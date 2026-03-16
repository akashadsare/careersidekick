# Portal Failure Modes — Documented Issues and Workarounds

**Phase 0 Deliverable — M0.5**  
**Date:** 16 March 2026  
**Status:** v0.1 — Initial Investigation

This document catalogs failure modes encountered during TinyFish portal integration spikes. Each entry includes:
- **Trigger condition** — When/how the failure occurs
- **Portal(s) affected** — Which ATS systems encounter this
- **Severity** — Critical (blocks all forms), High (common), Medium (occasional), Low (rare)
- **Workaround** — Mitigation or recovery strategy
- **Production impact** — How to handle in submission workflows

---

## 1. CAPTCHA Challenges

### Trigger

User's IP address or browser profile triggers CAPTCHA verification during form navigation or submission.

### Portals Affected

- Greenhouse: ~5–10% of applications (varies by IP reputation)
- Lever: ~3–8%
- Workday: ~2–5% (less common; Workday trusts browser profiles)
- LinkedIn: ~1–3% (LinkedIn is lenient on Easy Apply)

### Severity

**Critical** — Blocks all further progress; TinyFish cannot solve CAPTCHAs programmatically.

### Root Causes

- IP address flagged as datacenter/proxy
- Browser fingerprint detected as non-standard
- High volume of requests from same IP
- Geographic mismatch (application from unexpected location)

### Workarounds

#### Short-term (Phase 1)

1. **Return early:** When CAPTCHA detected, return error_code: `captcha_encountered` and `status: failure`
2. **Manual intervention:** Route to human review queue; human solves CAPTCHA
3. **IP rotation:** If possible, rotate through residential proxy pool
4. **Browser profile:** Use `browser_profile: 'full'` instead of `'lite'` to improve fingerprint authenticity

#### Medium-term (Phase 2)

1. Integrate CAPTCHA-solving service (e.g., 2Captcha, Anti-Captcha) if terms permit
2. Build user feedback loop: "CAPTCHA encountered; please solve and re-trigger" flow
3. Batch applications by IP to reduce triggering frequency
4. Implement adaptive backoff: if CAPTCHA occurs, wait 24 hours before attempting same portal from same IP

#### Long-term (Phase 3+)

1. Negotiate direct API access with tier-1 portals (Greenhouse, Lever, Workday)
2. Partner with ATS platforms on approved automation channel

### Production Impact

- **Success rate impact:** -5% to -15% depending on IP reputation
- **User experience:** Blocked run requires manual intervention; estimated 5–10 minute delay
- **Tracking:** Log CAPTCHA encounters by IP, portal, and time; analyze patterns

### Monitoring

```python
# Track CAPTCHA rate by portal
captcha_encounters = {
    'greenhouse': 7,
    'lever': 4,
    'workday': 1,
}
total_attempts = 100
captcha_rate = {k: v / total_attempts for k, v in captcha_encounters.items()}
# Expected: greenhouse ~7%, lever ~4%, workday ~1%
```

---

## 2. Account Creation / Login Requirements

### Trigger

User is not already logged into the ATS; portal requires account creation or login before applying.

### Portals Affected

- **Greenhouse:** Usually not required if accessing public job post; login required for saved applications
- **Lever:** Not required for standard applications
- **Workday:** Very common; many companies require account creation
- **Ashby:** Not required for public postings
- **LinkedIn:** Not required if already logged in via browser session

### Severity

**High** — Adds complexity; requires secure credential management.

### Root Causes

- Company privacy policy (some require tracked logins for all applicants)
- Workday best practice (all Workday adoptions implement account tracking)
- Recurring applicant tracking (portal checks if email exists)

### Workarounds

#### Phase 1

1. **Detect and stop:** If login screen detected, return error_code: `account_creation_required` and status: `failure`
2. **Prompt user:** Show "Portal requires login/account. Please log in manually and retry."
3. **Session reuse:** After manual login, cache session cookie; attempt to reuse for next application

#### Phase 2

1. **Credential vault:** Build secure credential storage for username/password pairs per portal
   - Encrypt passwords at rest (field-level encryption)
   - Use customer-provided credentials only
   - Support password managers (OAuth alternative)
2. **Account creation automation:** For Workday and similar:
   - Detect "Create account" flow
   - Extract form fields required (usually email, password, personal info)
   - Fill with candidate profile; use temporary password
   - Email temporary password to candidate securely
   - Resume application with new account

#### Phase 3

1. **SSO integration:** Support SAML/OAuth where portal allows
2. **Headless browser re-auth:** Manage sessions across runs more intelligently

### Production Impact

- **Success rate impact:** -10% to -30% depending on portal mix
- **User burden:** Manual login step needed per company (or per session)
- **Security:** Requires compliance with credential storage regulations

### Security Considerations

🚨 **Never log plain-text passwords.**  
🚨 **Always encrypt credentials at rest.**  
🚨 **Provide audit trail of who accessed which credentials.**

---

## 3. File Upload Failures

### Trigger

Resume or document upload fails during application submission.

### Portals Affected

- All portals support file uploads
- Failures vary by file size, format, network conditions

### Severity

**High** — Without resume, application is incomplete or auto-rejected.

### Root Causes

- **Network timeout:** Upload stalls or connection drops mid-transfer
- **File format issues:** Portal rejects PDF, DOCX, or hybrid format
- **File size limits:** Resume larger than portal's maximum (typically 5–10 MB)
- **Virus scan:** Portal's antivirus service flags file as suspicious
- **Session timeout:** Upload attempt after session expires
- **Disk quota:** Portal's file storage temporarily full (rare)

### Workarounds

#### Phase 1

1. **Pre-flight checks:**
   - Verify resume file exists and is readable
   - Check file size against portal specs (store per-portal limits in config)
   - Validate MIME type (application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document)

2. **Retry strategy:**
   - On upload failure, retry up to 2 times with exponential backoff (500ms, 2s)
   - If all retries fail, return error_code: `file_upload_failed`

3. **Format conversion:**
   - Offer "convert to PDF" option if original is DOCX and portal rejects

#### Phase 2

1. **Resume validation service:** Use external service (Affinda, Doxo) to pre-validate resume before upload
2. **Virus scan:** Pre-scan resume locally to avoid portal blocking
3. **Fallback resume:** If primary resume fails, offer candidate option to upload alternate format
4. **Resume optimization:** Auto-compress PDFs to reduce size while maintaining quality

#### Phase 3

1. **Inline resume generation:** Generate optimized resume variant per job on-the-fly (vs. pre-uploaded static file)
2. **Direct API upload:** Negotiate direct upload endpoints with portals to bypass UI upload flow

### Production Impact

- **Submission success rate:** -3% to -8%
- **User experience:** If resume upload fails, application must be retried or submitted manually
- **Data loss:** Application state is usually lost; user must restart

### Monitoring

```
upload_failures = {
  'timeout': 12,
  'format_error': 3,
  'size_limit': 2,
  'virus_detected': 1,
  'unknown': 5,
}
```

---

## 4. Session Expiry

### Trigger

User's session with the ATS portal expires between form steps or during download of result page.

### Portals Affected

- All portals implement session timeouts
- **Workday:** 20–30 minute timeout (strictest)
- **Greenhouse:** 60 minute timeout
- **Lever:** 60 minute timeout
- **LinkedIn:** 60+ minute timeout (refreshes automatically)

### Severity

**Medium** — Requires re-authentication; can be retried.

### Root Causes

- Application form navigation takes longer than expected (e.g., if user stalls at a field, then agent resumes)
- Long form (Workday) with delays between sections
- Portal server restarts or load balancer timeout
- Network latency causing apparent inactivity

### Workarounds

#### Phase 1

1. **Detect session loss:**
   - If page redirects to login after form submit, session likely expired
   - Check for session-expired error messages or 401/403 HTTP codes

2. **Fail gracefully:**
   - Return error_code: `session_expired`
   - Advise user to retry; often succeeds on second attempt (session refreshes)

3. **Timing awareness:**
   - Log actual form completion time per portal
   - Set timeouts conservatively (expect longest observed time × 1.5)

#### Phase 2

1. **Session refresh:** Periodically send "keep-alive" requests or navigate to portal homepage to refresh session during long forms
2. **Checkpoint and resume:** Save application state at key form sections; if session expires, resume from last checkpoint (if portal supports)

#### Phase 3

1. **Parallel session management:** Maintain multiple session IDs; use secondary session if primary expires
2. **Preemptive re-auth:** Detect re-auth requirement before form submission; silently re-authenticate

### Production Impact

- **Submission success rate:** -2% to -5%
- **User wait time:** Adds 1–2 minute delay for retry
- **Tracking:** Separately track "session_expired" vs. "form_error" for analytics

---

## 5. Dynamic Form Fields and Conditional Rendering

### Trigger

Form fields appear/disappear based on previous answers or user selections; TinyFish must adapt to conditional logic.

### Portals Affected

- **Greenhouse:** Moderate (some screening questions are conditional)
- **Lever:** High (many companies use branching logic)
- **Workday:** Very high (complex multi-step wizard with heavy conditional logic)
- **Ashby:** Medium (some conditional fields)

### Severity

**High** — Miss conditional fields → incomplete application → auto-rejection.

### Root Causes

- JavaScript event handlers trigger field show/hide
- Form validation changes which fields are required
- Answer-dependent follow-ups (e.g., "Do you need sponsorship? [YES] → Show visa type field")

### Workarounds

#### Phase 1

1. **Explicit field mapping:** In prompt template, list all known dynamic fields and their trigger conditions:
   ```
   {
     "field_visa_type": {
       "appears_if": "needs_sponsorship == true",
       "question": "What visa type are you interested in?"
     }
   }
   ```

2. **Wait for stability:** After filling a field that triggers conditionals, wait 1–2 seconds for DOM to settle
3. **Re-scan form:** After each answer, re-scan visible form fields to detect new fields

#### Phase 2

1. **JavaScript observer:** Inject small JS script to log field visibility changes; helps identify conditional logic
2. **Decision tree:** Build portal-specific decision tree for each company (if they use Workday step X, also check fields Y and Z)
3. **Heuristic field detection:** Scan entire page for input/select/textarea elements, not just known field IDs

#### Phase 3

1. **Portal-specific adapters:** Hand-write portal and company-specific handling for known branching patterns
2. **ML-based field detection:** Train model on screenshots of same portal to identify field patterns

### Production Impact

- **Missed fields rate:** -5% to -15% depending on portal dynamicism
- **Application quality:** Incomplete answers lead to application rejection
- **Monitoring:** Track "missed_fields" alongside unanswered_questions

### Example: Workday Sponsorship Logic

```
User fills "Do you need sponsorship for work authorization?" → "Yes"
→ Workday conditionally shows:
  - Visa type (H1B, L1, etc.)
  - Sponsorship preference (willing / not willing)
If agent misses this conditional reveal, answers remain blank → application rejected
```

---

## 6. OTP (One-Time Password) / Email Verification

### Trigger

Portal sends OTP via email for account creation or login verification.

### Portals Affected

- **Workday:** Very common for first-time account creation
- **Greenhouse:** Rare (usually auto-verifies if user has recruiter relationship)
- **Lever:** Occasionally on company custom portals
- **LinkedIn:** Not required for easy apply (session-based)

### Severity

**Critical** — Cannot proceed without OTP; requires external email access.

### Root Causes

- Security best practice (verify email ownership)
- Company compliance requirement
- First-time account registration flow

### Workarounds

#### Phase 1

1. **Fail fast:** If OTP prompt detected and no OTP available, return error_code: `otp_required`
2. **Manual intervention:** Route to human review; human enters OTP
3. **OTP timeout:** Check for OTP in email inbox (if email access provided); wait up to 60 seconds

#### Phase 2

1. **Email monitoring:** Integrate email client (IMAP) to automatically retrieve OTP from inbox
   - Connect to candidate's email (with permission)
   - Search for OTP code in recent emails
   - Extract code and fill automatically
   - ⚠️ Requires careful privacy/security handling

2. **OTP prediction:** Some email domains use predictable OTP formats; attempt common patterns
3. **Account re-use:** Cache account credentials post-first-application; subsequent applications reuse account (no OTP needed)

#### Phase 3

1. **Pre-created accounts:** Work with companies to pre-create applicant accounts with OTP bypassed
2. **API alternative:** Switch to direct API integration (if portal offers) to skip OTP entirely

### Production Impact

- **Workday-specific:** First application requires OTP (~100% of new accounts); subsequent applications OK
- **Overall rate:** -5% to -15% depending on Workday prevalence in job mix
- **User burden:** High; must provide email access or solve OTP manually

⚠️ **Privacy:** Email access is sensitive; require explicit consent and audit logging.

---

## 7. Resume Parsing / Field Extraction Inaccuracies

### Trigger

Parsed resume data doesn't match TinyFish form field expectations; fields are filled with incorrect values.

### Portals Affected

- Not portal-specific; affects all forms using parsed resume data

### Severity

**Medium** — Application submitted but with wrong information; likely rejected.

### Root Causes

- Resume parser library (Affinda, Eden AI) misextracts email, phone, or dates
- Unusual resume formatting confuses parser
- Non-English resumes parsed incorrectly
- Years of experience calculation off by 1–2 years

### Workarounds

#### Phase 1

1. **Human confirmation:** After resume upload, prompt user to review parsed fields before proceeding
   - Show extracted name, email, phone, location, experience
   - Allow user to correct any errors before package generation

2. **Validation rules:**
   - Email must match regex pattern
   - Phone must be 10+ digits
   - Years of experience must be 0–70
   - Location must not be empty

3. **Fallback to user input:** If parser fails or low confidence, ask user to manually enter field

#### Phase 2

1. **Multi-parser ensemble:** Use 2–3 resume parsers (Affinda + Eden AI + regex-based); vote on best extraction
2. **OCR backup:** If structured parsing fails, fall back to optical character recognition (OCR) + LLM extraction
3. **User history:** Store user-corrected values; use for future resumes from same candidate

#### Phase 3

1. **Resume re-formatting:** Auto-refactor resume into template-based format before parsing (improves parser accuracy)
2. **ML model:** Train custom resume parser on company's historical resume corpus

### Production Impact

- **Data quality issue:** ~10% of applications contain 1+ incorrect parsed fields
- **Application rejection rate:** +5% to +10% due to bad data
- **User friction:** Manual review step adds 2–3 minutes per candidate

---

## 8. Portal Downtime / Unavailability

### Trigger

Portal is temporarily down for maintenance or experiencing service disruption.

### Portals Affected

- All portals (rare, but happens)
- **Workday:** Less frequent downtime (enterprise SLA); ~0.5 hours per month typical
- **Greenhouse:** ~1 hour per month typical outage
- **Lever:** ~30 minutes per month typical
- **Custom portals:** Higher variance; can be down for hours

### Severity

**Medium** — Transient; usually resolves without intervention.

### Root Causes

- Scheduled maintenance
- Unplanned service outage
- Networking issues (DNS, CDN)
- Server overload (common after job posting surge)

### Workarounds

#### Phase 1

1. **Detect unavailability:** Check for 5xx HTTP errors or connection refusal
2. **Early fail:** Return error_code: `portal_unavailable` and status: `failure`
3. **Retry later:** Queue for retry after 30 minute delay (default backoff)

#### Phase 2

1. **Intelligent retry:** 
   - First retry: 5 minute wait
   - Second retry: 15 minute wait
   - Third retry: 1 hour wait
2. **Status page monitoring:** Check portal status page for maintenance windows; delay runs during announced maintenance

#### Phase 3

1. **Predictive scheduling:** Schedule bulk runs during off-peak hours (typically 11 PM – 6 AM)
2. **Load balancing:** Distribute runs across time windows to smooth load

### Production Impact

- **Availability:** ~99.5% typical (4.5 hours downtime per month across all portals)
- **User experience:** Automatic retry minimizes friction; most applications succeed on retry
- **Tracking:** Separately track portal_unavailable vs. user_error

---

## 9. Partial Form Completion (User Abandonment)

### Trigger

User navigates away from form, closes browser, or loses internet connection mid-application.

### Portals Affected

- All portals (varies by user behavior)

### Severity

**Low** — Not a technical failure; user choice.

### Root Causes

- Network disconnection
- User closes browser (even accidentally)
- Form takes too long; user abandons
- User forgets and closes tab

### Workarounds

#### Phase 1

1. **Detect and report:** If TinyFish determines application was not fully submitted (form data not committed), report as `status: failed`, error_code: `incomplete_submission`
2. **Offer retry:** Show user: "Your application was not submitted. Would you like to retry?"

#### Phase 2

1. **Save drafts:** If portal supports drafts API, save form state after each section
2. **Resume from checkpoint:** Offer user ability to resume partial application instead of starting over
3. **Offline detection:** If user loses connectivity, queue for retry when online

#### Phase 3

1. **Form auto-save:** Periodically POST form state to portal (if supported) to preserve progress
2. **Session persistence:** Maintain session across user browser restart if portal allows

### Production Impact

- **Completion rate:** ~95% of initiated forms completed (5% user abandonment typical)
- **User experience:** No frustration if seamless retry available
- **Tracking:** Monitor abandonment rate as proxy for form complexity

---

## 10. Duplicate Application Prevention Failures

### Trigger

Application submitted to same company/role multiple times (user accidentally resubmits).

### Portals Affected

- All portals accept duplicate applications (no built-in deduplication)

### Severity

**Low** — Not a system failure, but bad user experience / application quality issue.

### Root Causes

- User clicks submit twice accidentally
- User retries after perceived failure (but first submission succeeded)
- Multiple candidates create applications to same roles

### Workarounds

#### Phase 1

1. **Pre-flight check:** Before initiating TinyFish run, query backend for prior submissions to same company/role
   - Query: `SELECT * WHERE user_id = ? AND company = ? AND role ≈ ? AND submitted_at > NOW() - 30 days`
   - If found, show warning: "You already applied to [Company] for [Role] on [Date]. Apply again?"

2. **User confirmation:** Require user click "Yes, submit again" to override warning

#### Phase 2

1. **Fingerprinting:** Use company + role + location as duplicate key (more accurate than exact title match)
2. **Grace period:** Allow one re-apply per 30 days, block within 30 days

#### Phase 3

1. **ML deduplication:** Use embeddings (vector similarity) to detect near-duplicate applications even if job IDs differ

### Production Impact

- **Duplicate rate:** ~5% without prevention; <1% with warning
- **User experience:** Clear warning prevents accidental resubmissions
- **Application quality:** Reduces spam/noise in recruiter inboxes

---

## 11. Summary Table: Failure Modes by Severity and Impact

| Failure Mode | Severity | Frequency | Workaround Phase | Success Rate Impact |
|---|---|---|---|---|
| CAPTCHA | Critical | 5–10% | Phase 1: Manual intervention | -5% to -15% |
| Account creation required | High | 10–30% | Phase 2: Credential vault | -10% to -30% |
| File upload failure | High | 3–8% | Phase 1: Pre-flight checks | -3% to -8% |
| Session expiry | Medium | 2–5% | Phase 1: Fail & retry | -2% to -5% |
| Dynamic form fields | High | 5–15% | Phase 2: Field tree mapping | -5% to -15% |
| OTP required | Critical (Workday) | 100% (new accounts) | Phase 2: Email integration | -5% to -15% |
| Resume parsing error | Medium | ~10% | Phase 1: User confirmation | -5% to -10% |
| Portal downtime | Medium | <1% | Phase 1: Retry backoff | <1% |
| Partial form completion | Low | ~5% | Phase 1: Resume from checkpoint | -5% |
| Duplicate application | Low | ~5% | Phase 1: Pre-flight warning | N/A (UX improvement) |

---

## 12. Phase 1 Acceptance Criteria

Before marking Phase 0 complete and moving to Phase 1, confirm:

- [ ] **Tested 3+ portals** with TinyFish submissions in test environment
- [ ] **Failure modes documented** for each portal (at least 5 modes per portal)
- [ ] **Workarounds identified** for critical failures (CAPTCHA, account creation, OTP)
- [ ] **Success rates baselined:** Greenhouse ≥70%, Lever ≥70%, Workday ≥60% (or documented why not)
- [ ] **Error codes standardized:** Shared taxonomy across all portals
- [ ] **Result schema validated:** JSON output matches spec exactly

---

**Version History**

| Version | Date | Changes |
|---------|------|---------|
| v0.1 | 16 Mar 2026 | Initial failures catalog covering 11 modes with workarounds |
