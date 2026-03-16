<script lang="ts">
  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

  let candidateName = 'Alex Chen';
  let candidateEmail = 'alex.chen@example.com';
  let candidateLocation = 'San Francisco, CA';
  let roleTitle = 'Software Engineer, Automation';
  let companyName = 'Acme Labs';

  let loading = false;
  let error = '';
  let saveMessage = '';

  let packageData: null | {
    draft_id: number;
    candidate_name: string;
    role_title: string;
    company_name: string;
    fit_score: number;
    cover_note: string;
    answers: Array<{ question: string; answer: string; provenance: string }>;
  } = null;

  async function generatePreview() {
    loading = true;
    error = '';
    try {
      const res = await fetch(`${API_BASE}/api/v1/packages/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_name: candidateName,
          candidate_email: candidateEmail,
          candidate_location: candidateLocation,
          role_title: roleTitle,
          company_name: companyName,
        }),
      });
      if (!res.ok) {
        throw new Error(`Preview failed: ${res.status}`);
      }
      const parsed = await res.json();
      packageData = parsed;
      localStorage.setItem('careersidekick_last_draft_id', String(parsed.draft_id));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading = false;
    }
  }

  function onAnswerInput(event: Event, index: number) {
    const target = event.currentTarget as HTMLTextAreaElement;
    updateAnswer(index, target.value);
  }

  function updateAnswer(index: number, value: string) {
    if (!packageData) return;
    packageData.answers[index].answer = value;
    packageData = { ...packageData };
  }

  async function saveDraft(status: 'draft' | 'approved') {
    if (!packageData) return;

    saveMessage = '';
    error = '';
    try {
      const res = await fetch(`${API_BASE}/api/v1/drafts/${packageData.draft_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cover_note: packageData.cover_note,
          answers_json: { answers: packageData.answers },
          status,
        }),
      });

      if (!res.ok) {
        throw new Error(`Save failed: ${res.status}`);
      }

      saveMessage = status === 'approved' ? 'Draft approved and saved.' : 'Draft saved.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    }
  }
</script>

<section class="card panel">
  <h2>Application Approval Panel</h2>
  <p class="muted">Hard screen #1: role package review before submit.</p>

  <div class="grid">
    <label>
      Candidate
      <input class="input" bind:value={candidateName} />
    </label>
    <label>
      Candidate email
      <input class="input" bind:value={candidateEmail} />
    </label>
    <label>
      Candidate location
      <input class="input" bind:value={candidateLocation} />
    </label>
    <label>
      Role title
      <input class="input" bind:value={roleTitle} />
    </label>
    <label>
      Company
      <input class="input" bind:value={companyName} />
    </label>
  </div>

  <div class="toolbar">
    <button class="btn primary" on:click={generatePreview} disabled={loading}>
      {loading ? 'Generating...' : 'Generate package preview'}
    </button>
  </div>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  {#if packageData}
    <div class="summary card">
      <div>
        <h3>{packageData.role_title}</h3>
        <p class="muted">{packageData.company_name}</p>
        <p class="muted">Draft ID: {packageData.draft_id}</p>
      </div>
      <div class="fit">Fit score: <strong>{packageData.fit_score}</strong></div>
    </div>

    <div class="block">
      <h4>Cover note</h4>
      <textarea class="textarea" rows="4" bind:value={packageData.cover_note}></textarea>
    </div>

    <div class="block">
      <h4>Screening answers</h4>
      {#each packageData.answers as qa, i}
        <div class="qa card">
          <p><strong>Q:</strong> {qa.question}</p>
          <textarea
            class="textarea"
            rows="3"
            value={qa.answer}
            on:input={(e) => onAnswerInput(e, i)}
          ></textarea>
          <p class="muted">Source: {qa.provenance}</p>
        </div>
      {/each}
    </div>

    <div class="toolbar">
      <button class="btn" on:click={() => saveDraft('draft')}>Save as draft</button>
      <button class="btn primary" on:click={() => saveDraft('approved')}>Approve package</button>
    </div>

    {#if saveMessage}
      <p class="success">{saveMessage}</p>
    {/if}
  {/if}
</section>

<style>
  .panel {
    padding: 20px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
    margin-top: 12px;
  }

  label {
    display: grid;
    gap: 6px;
    font-size: 14px;
  }

  .toolbar {
    display: flex;
    gap: 10px;
    margin-top: 14px;
    flex-wrap: wrap;
  }

  .summary {
    margin-top: 16px;
    padding: 14px;
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
  }

  .fit {
    background: var(--accent-soft);
    padding: 8px 12px;
    border-radius: 10px;
  }

  .block {
    margin-top: 16px;
  }

  .qa {
    margin-top: 10px;
    padding: 12px;
  }

  .qa p {
    margin: 0 0 8px;
  }

  .error {
    color: #b42318;
    margin-top: 10px;
  }

  .success {
    color: #2b6b2d;
    margin-top: 10px;
  }
</style>
