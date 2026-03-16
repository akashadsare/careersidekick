<script lang="ts">
  import { onMount } from 'svelte';

  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

  let targetUrl = 'https://scrapeme.live/shop';
  let goal = 'Extract the first 3 product names and prices. Return as JSON.';
  let browserProfile: 'lite' | 'stealth' = 'lite';

  let running = false;
  let executionId = '';
  let draftId = '';
  let streamingUrl = '';
  let progress: string[] = [];
  let resultJson = '';
  let error = '';
  let runsLoading = false;

  type RunHistory = {
    id: number;
    draft_id: number | null;
    tinyfish_run_id: string | null;
    run_status: string;
    started_at: string | null;
    finished_at: string | null;
    duration_ms: number | null;
    streaming_url: string | null;
    error_message: string | null;
    created_at: string;
  };

  type RunDetail = RunHistory & {
    result_json: Record<string, unknown> | null;
  };

  type ExecutionMetrics = {
    window_days: number;
    total_runs: number;
    completed_runs: number;
    failed_runs: number;
    cancelled_runs: number;
    running_runs: number;
    success_rate: number;
    avg_duration_ms: number | null;
    failures_by_day: Array<{ day: string; count: number }>;
  };

  let runHistory: RunHistory[] = [];
  let selectedRun: RunDetail | null = null;
  let filterStatus = '';
  let filterDraftId = '';
  let historyLimit = '25';
  let sortDirection: 'asc' | 'desc' = 'desc';
  let historyCursor: number | null = null;
  let nextCursor: number | null = null;
  let hasMore = false;
  let totalCount = 0;
  let cursorStack: Array<number | null> = [null];
  let statusUpdating = false;
  let metricsLoading = false;
  let metricsWindowDays = '30';
  let metrics: ExecutionMetrics | null = null;
  let metricsError = '';

  function statusClass(status: string): string {
    if (status === 'completed') return 'status completed';
    if (status === 'failed') return 'status failed';
    if (status === 'running') return 'status running';
    if (status === 'cancelled') return 'status cancelled';
    return 'status';
  }

  function formatDuration(durationMs: number | null): string {
    if (durationMs === null) return '-';
    if (durationMs < 1000) return `${durationMs} ms`;

    const seconds = durationMs / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)} s`;

    const minutes = Math.floor(seconds / 60);
    const remSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remSeconds}s`;
  }

  function buildFailureTrendPoints(buckets: Array<{ day: string; count: number }>): string {
    if (buckets.length <= 1) return '';

    const width = 360;
    const height = 120;
    const maxCount = Math.max(...buckets.map((bucket) => bucket.count), 1);

    return buckets
      .map((bucket, index) => {
        const x = (index / (buckets.length - 1)) * width;
        const y = height - (bucket.count / maxCount) * height;
        return `${x},${y}`;
      })
      .join(' ');
  }

  async function loadMetrics() {
    metricsLoading = true;
    metricsError = '';
    try {
      const params = new URLSearchParams();
      if (metricsWindowDays) params.set('days', metricsWindowDays);
      const res = await fetch(`${API_BASE}/api/v1/executions/metrics?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Metrics load failed: ${res.status}`);
      }
      metrics = await res.json();
    } catch (e) {
      metricsError = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      metricsLoading = false;
    }
  }

  function initializeFromUrlQuery() {
    if (typeof window === 'undefined') return null;

    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    const draftId = params.get('draft_id');
    const limit = params.get('limit');
    const sort = params.get('sort_direction');
    const runId = params.get('run_id');

    if (status && ['running', 'completed', 'failed', 'cancelled'].includes(status)) {
      filterStatus = status;
    }
    if (draftId) {
      filterDraftId = draftId;
    }
    if (limit) {
      historyLimit = limit;
    }
    if (sort === 'asc' || sort === 'desc') {
      sortDirection = sort;
    }

    if (runId) {
      const parsed = Number(runId);
      if (Number.isFinite(parsed) && parsed > 0) {
        return parsed;
      }
    }

    return null;
  }

  async function loadRunHistory() {
    runsLoading = true;
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status', filterStatus);
      if (filterDraftId) params.set('draft_id', filterDraftId);
      if (historyLimit) params.set('limit', historyLimit);
      if (historyCursor !== null) params.set('cursor', String(historyCursor));
      params.set('sort_direction', sortDirection);
      const query = params.toString();

      const res = await fetch(`${API_BASE}/api/v1/executions/page${query ? `?${query}` : ''}`);
      if (!res.ok) {
        throw new Error(`History load failed: ${res.status}`);
      }
      const payload = await res.json();
      runHistory = payload.data;
      nextCursor = payload.pagination.next_cursor;
      hasMore = payload.pagination.has_more;
      totalCount = payload.pagination.total_count;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      runsLoading = false;
    }
  }

  async function applyFilters() {
    historyCursor = null;
    nextCursor = null;
    hasMore = false;
    cursorStack = [null];
    await loadRunHistory();
  }

  async function nextPage() {
    if (!hasMore || nextCursor === null) return;
    historyCursor = nextCursor;
    cursorStack = [...cursorStack, historyCursor];
    await loadRunHistory();
  }

  async function previousPage() {
    if (cursorStack.length <= 1) return;
    const newStack = cursorStack.slice(0, -1);
    cursorStack = newStack;
    historyCursor = newStack[newStack.length - 1] ?? null;
    await loadRunHistory();
  }

  async function loadRunDetail(id: number) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/executions/${id}`);
      if (!res.ok) {
        throw new Error(`Detail load failed: ${res.status}`);
      }
      selectedRun = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    }
  }

  async function updateSelectedRunStatus(nextStatus: 'running' | 'completed' | 'failed' | 'cancelled') {
    if (!selectedRun) return;

    statusUpdating = true;
    const previousSelected = { ...selectedRun };
    const previousHistory = [...runHistory];

    selectedRun = { ...selectedRun, run_status: nextStatus };
    runHistory = runHistory.map((run) => (run.id === selectedRun?.id ? { ...run, run_status: nextStatus } : run));

    try {
      const res = await fetch(`${API_BASE}/api/v1/executions/${selectedRun.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_status: nextStatus }),
      });
      if (!res.ok) {
        throw new Error(`Status update failed: ${res.status}`);
      }
      await loadRunDetail(selectedRun.id);
      await loadRunHistory();
      await loadMetrics();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
      selectedRun = previousSelected;
      runHistory = previousHistory;
    } finally {
      statusUpdating = false;
    }
  }

  async function startRun() {
    running = true;
    executionId = '';
    streamingUrl = '';
    progress = [];
    resultJson = '';
    error = '';

    try {
      draftId = localStorage.getItem('careersidekick_last_draft_id') ?? '';

      const res = await fetch(`${API_BASE}/api/v1/executions/run-sse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: targetUrl,
          goal,
          browser_profile: browserProfile,
          draft_id: draftId ? Number(draftId) : null,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Run start failed: ${res.status}`);
      }

      executionId = res.headers.get('X-Execution-Id') ?? '';

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === 'PROGRESS' && event.purpose) {
              progress = [...progress, event.purpose];
            }
            if (event.type === 'STREAMING_URL' && event.streamingUrl) {
              streamingUrl = event.streamingUrl;
            }
            if (event.type === 'COMPLETE') {
              if (event.status === 'COMPLETED') {
                resultJson = JSON.stringify(event.resultJson ?? {}, null, 2);
              } else {
                error = event.error?.message ?? 'Run failed';
              }
              running = false;
              await loadRunHistory();
              await loadMetrics();
            }
          } catch {
            // Ignore non-JSON chunks.
          }
        }
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
      running = false;
    }
  }

  onMount(async () => {
    const initialRunId = initializeFromUrlQuery();
    await loadRunHistory();
    await loadMetrics();
    if (initialRunId !== null) {
      await loadRunDetail(initialRunId);
    }
  });
</script>

<section class="card panel">
  <h2>Live Run Viewer</h2>
  <p class="muted">Hard screen #2: TinyFish SSE run monitor + streaming iframe.</p>

  <div class="grid">
    <label>
      Target URL
      <input class="input" bind:value={targetUrl} />
    </label>
    <label>
      Browser profile
      <select class="select" bind:value={browserProfile}>
        <option value="lite">lite</option>
        <option value="stealth">stealth</option>
      </select>
    </label>
  </div>

  <label class="goal">
    Goal
    <textarea class="textarea" rows="4" bind:value={goal}></textarea>
  </label>

  <div class="toolbar">
    <button class="btn primary" on:click={startRun} disabled={running}>
      {running ? 'Running...' : 'Start TinyFish run'}
    </button>
    <button class="btn" on:click={loadRunHistory} disabled={runsLoading}>
      {runsLoading ? 'Loading...' : 'Refresh run history'}
    </button>
    <button class="btn" on:click={previousPage} disabled={runsLoading || cursorStack.length <= 1}>Previous page</button>
    <button class="btn" on:click={nextPage} disabled={runsLoading || !hasMore}>Next page</button>
  </div>

  <div class="filters card">
    <label>
      Filter status
      <select class="select" bind:value={filterStatus}>
        <option value="">All</option>
        <option value="running">running</option>
        <option value="completed">completed</option>
        <option value="failed">failed</option>
        <option value="cancelled">cancelled</option>
      </select>
    </label>
    <label>
      Filter draft ID
      <input class="input" bind:value={filterDraftId} placeholder="e.g. 12" />
    </label>
    <label>
      Limit
      <input class="input" bind:value={historyLimit} placeholder="25" />
    </label>
    <label>
      Sort
      <select class="select" bind:value={sortDirection}>
        <option value="desc">Newest first</option>
        <option value="asc">Oldest first</option>
      </select>
    </label>
    <button class="btn" on:click={applyFilters} disabled={runsLoading}>Apply filters</button>
  </div>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <p class="muted">
    {#if draftId}
      Draft ID: <strong>{draftId}</strong>
    {:else}
      Draft ID: none (generate a package first from Approval Panel)
    {/if}
    {#if executionId}
      | Execution ID: <strong>{executionId}</strong>
    {/if}
  </p>

  <div class="layout">
    <div class="card pane">
      <h3>Execution trace</h3>
      {#if progress.length === 0}
        <p class="muted">No steps yet.</p>
      {:else}
        <ol>
          {#each progress as step}
            <li>{step}</li>
          {/each}
        </ol>
      {/if}
    </div>

    <div class="card pane">
      <h3>Live browser</h3>
      {#if streamingUrl}
        <iframe src={streamingUrl} title="TinyFish live run" loading="lazy"></iframe>
      {:else}
        <p class="muted">Waiting for STREAMING_URL event...</p>
      {/if}
    </div>
  </div>

  <div class="card result">
    <h3>Result JSON</h3>
    <pre>{resultJson || 'No result yet.'}</pre>
  </div>

  <div class="card result">
    <h3>Execution metrics</h3>
    <div class="toolbar compact">
      <label>
        Window (days)
        <input class="input" bind:value={metricsWindowDays} placeholder="30" />
      </label>
      <button class="btn" on:click={loadMetrics} disabled={metricsLoading}>
        {metricsLoading ? 'Loading metrics...' : 'Refresh metrics'}
      </button>
    </div>

    {#if metricsError}
      <p class="error">{metricsError}</p>
    {/if}

    {#if metrics}
      <div class="metrics-grid">
        <div class="timeline-item card">
          <p><strong>Total runs</strong></p>
          <p class="muted">{metrics.total_runs}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Success rate</strong></p>
          <p class="muted">{metrics.success_rate}%</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Avg duration</strong></p>
          <p class="muted">{formatDuration(metrics.avg_duration_ms)}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Running</strong></p>
          <p class="muted">{metrics.running_runs}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Failed</strong></p>
          <p class="muted">{metrics.failed_runs}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Cancelled</strong></p>
          <p class="muted">{metrics.cancelled_runs}</p>
        </div>
      </div>

      <h4>Failures by day</h4>
      {#if metrics.failures_by_day.length === 0}
        <p class="muted">No failures in selected window.</p>
      {:else}
        {#if metrics.failures_by_day.length > 1}
          <div class="trend card">
            <p><strong>Failure trend (daily)</strong></p>
            <svg viewBox="0 0 360 120" role="img" aria-label="Failure trend by day">
              <polyline
                points={buildFailureTrendPoints(metrics.failures_by_day)}
                fill="none"
                stroke="var(--text)"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <p class="muted">
              {metrics.failures_by_day[0].day} to {metrics.failures_by_day[metrics.failures_by_day.length - 1].day}
            </p>
          </div>
        {/if}

        <div class="history-table">
          <div class="row header metrics-row">
            <span>Day</span>
            <span>Count</span>
          </div>
          {#each metrics.failures_by_day as bucket}
            <div class="row metrics-row">
              <span>{bucket.day}</span>
              <span>{bucket.count}</span>
            </div>
          {/each}
        </div>
      {/if}
    {:else if !metricsLoading}
      <p class="muted">No metrics loaded yet.</p>
    {/if}
  </div>

  <div class="card result">
    <h3>Recent runs</h3>
    <p class="muted">
      Total: {totalCount} | Cursor: {historyCursor ?? 'start'} | Next: {nextCursor ?? 'none'} | Has more: {hasMore ? 'yes' : 'no'}
    </p>
    {#if runHistory.length === 0}
      <p class="muted">No run records yet.</p>
    {:else}
      <div class="history-table">
        <div class="row header">
          <span>ID</span>
          <span>Draft</span>
          <span>Status</span>
          <span>TinyFish Run</span>
          <span>Duration</span>
          <span>Created</span>
        </div>
        {#each runHistory as run}
          <button class="row" on:click={() => loadRunDetail(run.id)}>
            <span>{run.id}</span>
            <span>{run.draft_id ?? '-'}</span>
            <span><span class={statusClass(run.run_status)}>{run.run_status}</span></span>
            <span>{run.tinyfish_run_id ?? '-'}</span>
            <span>{formatDuration(run.duration_ms)}</span>
            <span>{new Date(run.created_at).toLocaleString()}</span>
          </button>
          {#if run.error_message}
            <p class="muted">Run {run.id} error: {run.error_message}</p>
          {/if}
        {/each}
      </div>
    {/if}
  </div>

  <div class="card result">
    <h3>Selected run details</h3>
    {#if selectedRun}
      <p class="muted">
        Run {selectedRun.id} |
        <span class={statusClass(selectedRun.run_status)}>{selectedRun.run_status}</span>
      </p>
      <div class="timeline">
        <div class="timeline-item card">
          <p><strong>Created</strong></p>
          <p class="muted">{new Date(selectedRun.created_at).toLocaleString()}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>TinyFish Run ID</strong></p>
          <p class="muted">{selectedRun.tinyfish_run_id ?? 'Not assigned yet'}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Started</strong></p>
          <p class="muted">{selectedRun.started_at ? new Date(selectedRun.started_at).toLocaleString() : 'Not recorded'}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Finished</strong></p>
          <p class="muted">{selectedRun.finished_at ? new Date(selectedRun.finished_at).toLocaleString() : 'Not recorded'}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Duration</strong></p>
          <p class="muted">{selectedRun.duration_ms !== null ? formatDuration(selectedRun.duration_ms) : 'Not recorded'}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Streaming URL</strong></p>
          <p class="muted">{selectedRun.streaming_url ?? 'Not available'}</p>
        </div>
        <div class="timeline-item card">
          <p><strong>Error</strong></p>
          <p class="muted">{selectedRun.error_message ?? 'No error recorded'}</p>
        </div>
      </div>
      <div class="toolbar">
        <button class="btn" disabled={statusUpdating} on:click={() => updateSelectedRunStatus('running')}>Set running</button>
        <button class="btn" disabled={statusUpdating} on:click={() => updateSelectedRunStatus('completed')}>Set completed</button>
        <button class="btn" disabled={statusUpdating} on:click={() => updateSelectedRunStatus('failed')}>Set failed</button>
        <button class="btn" disabled={statusUpdating} on:click={() => updateSelectedRunStatus('cancelled')}>Set cancelled</button>
      </div>
      <pre>{JSON.stringify(selectedRun.result_json ?? { note: 'No result payload stored.' }, null, 2)}</pre>
    {:else}
      <p class="muted">Click a row in Recent runs to view full details.</p>
    {/if}
  </div>
</section>

<style>
  .panel {
    padding: 20px;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 220px;
    gap: 12px;
  }

  label {
    display: grid;
    gap: 6px;
    font-size: 14px;
  }

  .goal {
    margin-top: 12px;
  }

  .toolbar {
    display: flex;
    gap: 10px;
    margin-top: 14px;
  }

  .toolbar.compact {
    margin-top: 8px;
    align-items: end;
    flex-wrap: wrap;
  }

  .filters {
    margin-top: 10px;
    padding: 10px;
    display: grid;
    grid-template-columns: 220px 220px 120px 160px 140px;
    gap: 10px;
    align-items: end;
  }

  .layout {
    margin-top: 16px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .pane {
    padding: 12px;
    min-height: 260px;
  }

  iframe {
    width: 100%;
    min-height: 220px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface-soft);
  }

  .result {
    margin-top: 12px;
    padding: 12px;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .error {
    color: #b42318;
    margin-top: 10px;
  }

  .history-table {
    display: grid;
    gap: 6px;
  }

  .row {
    display: grid;
    grid-template-columns: 60px 70px 110px 1fr 110px 190px;
    gap: 8px;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 13px;
    text-align: left;
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
  }

  .row.header {
    font-weight: 600;
    background: var(--surface-soft);
  }

  .status {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    border: 1px solid var(--border);
  }

  .status.running {
    background: #fff7dd;
    color: #8a6414;
  }

  .status.completed {
    background: #e8f6e8;
    color: #1f6b36;
  }

  .status.failed {
    background: #fde8e8;
    color: #a01818;
  }

  .status.cancelled {
    background: #ececec;
    color: #4b4b4b;
  }

  .timeline {
    display: grid;
    gap: 8px;
    margin-bottom: 10px;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin: 10px 0;
  }

  .metrics-row {
    grid-template-columns: 1fr 90px;
    cursor: default;
  }

  .trend {
    margin-bottom: 10px;
    padding: 10px;
  }

  .trend svg {
    width: 100%;
    max-width: 520px;
    height: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface-soft);
    display: block;
  }

  .timeline-item {
    padding: 10px;
  }

  .timeline-item p {
    margin: 0;
  }

  @media (max-width: 900px) {
    .grid,
    .layout {
      grid-template-columns: 1fr;
    }

    .filters {
      grid-template-columns: 1fr;
    }

    .row {
      grid-template-columns: 1fr;
    }

    .metrics-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
