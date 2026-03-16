# TinyFish Goal Prompts — Portal Execution Templates

**Phase 0 Deliverable**  
**Date:** 16 March 2026  
**Status:** v0.1 — Validation Stage

This document defines TinyFish goal prompts for tier-1 ATS portals. Each prompt is designed to:
1. Navigate the portal's application flow
2. Fill structured fields from candidate data
3. Stop at confirmation screen (do not auto-submit unless explicitly marked)
4. Capture structured result with success or failure reason

---

## 1. Greenhouse Portal Submission Prompt

**Target Portal:** Greenhouse-hosted job postings  
**Success Rate Target (Phase 1):** ≥ 70%  
**Last Validated:** 16 March 2026

### Goal Prompt

```
You are a job application automation agent. Your task is to complete a job application 
on a Greenhouse-hosted career portal.

**Input Data:**
- Candidate full name: {candidate_name}
- Candidate email: {candidate_email}
- Candidate location: {candidate_location}
- Phone: {phone}
- Years of experience: {years_experience}
- Resume URL (pre-uploaded): {resume_url}
- Cover note: {cover_note}
- Answer to "Are you authorized to work in {country}?": {work_auth_answer}
- LinkedIn profile URL: {linkedin_url}
- Preferred work model: {work_model}

**Application Flow:**
1. Check if the job posting is still open. If job status shows "Closed", stop and return
   error: "job_closed"
2. Click the "Apply now" or "Apply" button.
3. On the application form:
   - Enter full name in the "Full name" or "Name" field
   - Enter email in "Email" field
   - Enter phone in "Phone" field (if present)
   - Enter location in Location field (if present)
   - Upload resume from {resume_url} using the file upload field
   - Enter LinkedIn URL in the appropriate field (if present)
   - For screening questions:
     * If "Are you authorized to work...?" appears, fill with: {work_auth_answer}
     * If "Preferred work model/location" appears, fill with: {work_model}
     * If any other screening question appears and you have a matching answer, fill it
     * If a question has no matching data, do NOT fabricate; return as unanswered
4. Add cover note to the "Cover letter" or "Additional info" field if present (content: {cover_note})
5. **Do NOT click submit.** Navigate to the final review page that shows all entered data.
6. Once on the review page, capture:
   - Page title or heading (to confirm you're at review)
   - All visible filled fields
   - Screenshot of the full form

**Result Schema (return as JSON):**
{
  "status": "success" | "failure",
  "error_code": null | "job_closed" | "form_error" | "file_upload_failed" | "captcha_encountered" | "session_expired" | "unknown",
  "error_message": "human readable error description or null",
  "reached_review_screen": true | false,
  "fields_filled": {
    "full_name": "captured value",
    "email": "captured value",
    "phone": "captured value",
    "location": "captured value",
    "work_auth": "captured value",
    "work_model": "captured value",
    "cover_note": "captured value or null"
  },
  "unanswered_questions": ["list of questions left blank"],
  "final_screenshot": "base64_encoded_image or url"
}
```

### Field Mapping

| Greenhouse Field Label | Extracted From | Fallback |
|---|---|---|
| Full name / Name | candidate_name | (required) |
| Email | candidate_email | (required) |
| Phone | phone | (optional, skip if not present) |
| Location / City | candidate_location | (optional) |
| Resume / CV | {resume_url} | (required, failure if missing) |
| LinkedIn | linkedin_url | (optional) |

### Stop Conditions

**STOP and return `success`:**
- Form review page reached with all required fields filled

**STOP and return `failure`:**
- CAPTCHA encountered → error_code: `captcha_encountered`
- File upload fails → error_code: `file_upload_failed`
- Job posting status shows "Closed" → error_code: `job_closed`
- Form validation error (e.g., invalid email) → error_code: `form_error`
- Session expires or portal becomes unresponsive → error_code: `session_expired`

---

## 2. Lever Portal Submission Prompt

**Target Portal:** Lever-hosted job postings  
**Success Rate Target:** ≥ 70%  
**Last Validated:** 16 March 2026

### Goal Prompt

```
You are a job application automation agent. Complete a job application on a Lever-hosted portal.

**Input Data:**
- Candidate full name: {candidate_name}
- Candidate email: {candidate_email}
- Candidate phone: {phone}
- Candidate location: {candidate_location}
- Years of experience: {years_experience}
- Resume URL (pre-uploaded): {resume_url}
- Cover note: {cover_note}
- Work authorization status: {work_auth_answer}
- Desired work arrangement: {work_model}

**Application Flow:**
1. Navigate to the application form. Check for any "This position has been filled" or closed indicators. 
   If found, stop with error_code: "job_closed"
2. Fill in the standard fields:
   - Name → {candidate_name}
   - Email → {candidate_email}
   - Phone → {phone}
   - Location (if multi-choice) → {candidate_location}
3. For the resume/CV field: 
   - Click "Upload document" or similar
   - Upload resume from {resume_url}
   - Wait for upload confirmation
4. For screening questions (Lever typically shows these):
   - "Are you looking for..." (employment type) → fill with {work_model}
   - "Are you eligible to work..." → fill with {work_auth_answer}
   - Any other questions → check if we have matching data; if not, skip
5. Optionally fill cover letter field with: {cover_note}
6. **Do NOT click submit.** Navigate to the review/confirmation screen.
7. Capture screenshot and all visible field values.

**Result Schema:**
{
  "status": "success" | "failure",
  "error_code": null | "job_closed" | "form_error" | "file_upload_failed" | "captcha_encountered" | "session_expired" | "unknown",
  "error_message": "human readable error",
  "reached_review_screen": true | false,
  "fields_filled": {
    "full_name": "captured",
    "email": "captured",
    "phone": "captured",
    "location": "captured",
    "work_auth": "captured",
    "work_model": "captured"
  },
  "unanswered_questions": ["list of questions"],
  "final_screenshot": "base64 or url"
}
```

### Field Mapping

| Lever Field | Source | Optional |
|---|---|---|
| Your name | candidate_name | No |
| Email | candidate_email | No |
| Phone | phone | Yes |
| Location | candidate_location | Yes |
| Resume / CV | {resume_url} | No |
| How are you looking to work? | work_model | Yes |
| Are you authorized to work...? | work_auth_answer | No |

### Stop Conditions

Same as Greenhouse: CAPTCHA, upload failure, job closed, session expiry, or successful review screen reach.

---

## 3. Workday Portal Submission Prompt (Draft Mode)

**Target Portal:** Workday-hosted job postings  
**Success Rate Target:** ≥ 60% (Phase 2)  
**Note:** Do not auto-submit. Stop at review page only.  
**Last Validated:** 16 March 2026

### Goal Prompt

```
Complete a job application on a Workday-hosted career portal. **DO NOT SUBMIT** — stop at preview/review.

**Input Data:**
- Candidate full name: {candidate_name}
- Email: {candidate_email}
- Phone: {phone}
- Location: {candidate_location}
- Years of relevant experience: {years_experience}
- Resume URL: {resume_url}
- Desired work type (Remote/Hybrid/Onsite): {work_model}
- Work authorization: {work_auth_answer}
- Cover note: {cover_note}

**Application Flow:**
1. Locate the "Apply" button/link on the job posting.
2. Click to open the application form.
3. Workday may redirect to a login screen:
   - If new user required: Workday will prompt for account creation (email + password)
   - Use provided candidate_email for account creation
   - Use a temporary password (can be system-generated or candidate-provided)
4. Fill the application form:
   - Full Name → {candidate_name}
   - Email → {candidate_email}
   - Phone → {phone}
   - Current Location → {candidate_location}
   - Years of Experience → {years_experience}
5. Upload resume:
   - Locate "Resume" or "Attachment" field
   - Upload file from {resume_url}
   - Confirm upload completes
6. For screening questions (common in Workday):
   - "Are you authorized to work in [country]?" → {work_auth_answer}
   - "Preferred work arrangement" → {work_model}
   - Others → skip if no matching data
7. **Critical: Do NOT click Submit.** 
   - Instead, look for "Review" or "Preview" button
   - Click to view the full application summary
   - Capture the review page screenshot

**Result Schema:**
{
  "status": "success" | "failure",
  "error_code": null | "account_creation_failed" | "file_upload_failed" | "captcha_encountered" | "otp_required" | "job_closed" | "session_expired" | "unknown",
  "error_message": "human readable",
  "account_created": true | false,
  "reached_review_screen": true | false,
  "fields_filled": {
    "full_name": "value",
    "email": "value",
    "phone": "value",
    "location": "value",
    "years_experience": "value",
    "work_auth": "value",
    "work_model": "value"
  },
  "unanswered_required_fields": ["list"],
  "final_screenshot": "base64 or url"
}
```

### Workday-Specific Notes

- **Account Creation:** Workday often requires new applicants to create an account. This is a valid flow.
- **OTP (One-Time Password):** If Workday sends an email OTP for verification, the agent should:
  - Wait up to 30 seconds for OTP to arrive
  - If no OTP arrives, return error_code: `otp_required` with status: `failure`
  - Do NOT attempt to bypass authentication
- **Session Timeout:** Workday sessions may expire after 20–30 minutes of inactivity; document in error_message if encountered.

### Stop Conditions

- CAPTCHA → stop, error_code: `captcha_encountered`
- OTP required but not available → stop, error_code: `otp_required`
- Account creation failure → stop, error_code: `account_creation_failed`
- File upload fails → stop, error_code: `file_upload_failed`
- Review screen reached successfully → stop with status: `success`

---

## 4. LinkedIn Easy Apply (Draft, ToS Review Required)

**Target Portal:** LinkedIn job postings with "Easy Apply" enabled  
**Success Rate Target:** TBD (Phase 1, post-legal review)  
**Status:** DO NOT SUBMIT — draft mode only pending ToS legal review  
**Last Validated:** N/A — pending legal review

### Legal/ToS Considerations

LinkedIn's Terms of Service explicitly restrict bot automation on Easy Apply flows. Before enabling this prompt:
1. Obtain legal review of ToS compliance
2. Determine if LinkedIn Easy Apply falls under "interactive non-transactional" exemption
3. Consult with LinkedIn developer program team on permitted automation use cases
4. Document consent/permission model for users

### Goal Prompt (Conditional on Legal Clearance)

```
**ONLY USE THIS PROMPT AFTER LEGAL REVIEW AND EXPLICIT USER CONSENT**

Complete the LinkedIn Easy Apply flow **in draft mode** — do not submit until user explicitly approves.

**Input Data:**
- Candidate name: {candidate_name}
- Candidate email: {candidate_email}
- Phone: {phone}
- LinkedIn profile (logged in): {linkedin_authenticated}
- Resume: {resume_url}
- Cover note: {cover_note}

**Application Flow:**
1. Assume user is already logged into LinkedIn
2. Locate the LinkedIn Easy Apply button on a job posting
3. Click to open the Easy Apply modal
4. LinkedIn will auto-fill profile-based fields (name, email, phone, profile headline)
5. For additional fields:
   - If resume field present: upload from {resume_url}
   - If screening questions present: answer from provided data
6. **Stop before final Submit** (do not click the "Submit application" button)
7. Capture state: show all entered/auto-filled fields

**Result Schema:**
{
  "status": "draft_ready" | "failure",
  "error_code": null | "captcha_encountered" | "authentication_required" | "session_expired" | "unknown",
  "error_message": "human readable",
  "auto_filled_fields": {
    "name": "value",
    "headline": "value",
    "email": "value",
    "phone": "value"
  },
  "user_filled_fields": { ... },
  "ready_for_submission": true | false,
  "screenshot": "base64 or url"
}
```

### Important Constraints

- **Cannot auto-submit** until explicit user approval in UI
- **No credential harvesting** from LinkedIn profiles
- **Session management:** Do not maintain persistent sessions; each run should re-authenticate or use existing session only
- **Rate limiting:** Respect LinkedIn's rate limits; do not attempt multiple submissions in rapid succession

---

## 5. Portal Prompt Validation Checklist

For each portal, before marking a prompt ready for production:

- [ ] **Field Extraction:** All required fields captured correctly from test candidate
- [ ] **File Upload:** Resume upload succeeds and file is retrievable
- [ ] **Screening Questions:** At least 3 common questions answered correctly
- [ ] **Error Handling:** CAPTCHA, session timeout, validation error cases tested
- [ ] **Review Screen:** Final review/preview page screenshot captured successfully
- [ ] **No Auto-Submit:** Prompt stops before submission for early phases
- [ ] **Result Schema:** JSON output matches spec exactly
- [ ] **Performance:** Prompt completes within 5 minutes for typical form (Workday may be longer due to account creation)

---

## 6. Next Steps (Phase 1)

Once prompts are validated on at least 3 portals:

1. Integrate prompt templates into TinyFish client wrapper
2. Build result parser to extract structured data
3. Add retry logic for transient failures (network timeouts, etc.)
4. Implement approval gate: show captured screenshot and fields to user before confirmation
5. Track success/failure rates by portal and reason code
6. Document failure mode workarounds (CAPTCHA bypass strategies, account creation flows, etc.)

---

**Version History**

| Version | Date | Changes |
|---------|------|---------|
| v0.1 | 16 Mar 2026 | Initial prompts for Greenhouse, Lever, Workday (draft), LinkedIn (ToS pending) |
