<script lang="ts">
  import { onMount } from 'svelte';

  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
  const DASHBOARD_PREFS_KEY = 'careersidekick_dashboard_prefs';

  type Metrics = {
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

  type RunRow = {
    id: number;
    draft_id: number | null;
    run_status: 'running' | 'completed' | 'failed' | 'cancelled';
    duration_ms: number | null;
    tinyfish_run_id: string | null;
    created_at: string;
  };

  let metrics: Metrics | null = null;
  let recentRuns: RunRow[] = [];
  let days = '30';
  let statusFilter: '' | 'running' | 'completed' | 'failed' | 'cancelled' = '';
  let successAlertThreshold = '80';
  let loading = false;
  let error = '';
  let prefsReady = false;

  $: parsedSuccessThreshold = Number(successAlertThreshold);
  $: hasValidThreshold = Number.isFinite(parsedSuccessThreshold) && parsedSuccessThreshold >= 0;
  $: showSuccessAlert =
    hasValidThreshold && metrics !== null && metrics.success_rate < parsedSuccessThreshold;

  function formatDuration(durationMs: number | null): string {
    if (durationMs === null) return '-';
    if (durationMs < 1000) return `${durationMs} ms`;

    const seconds = durationMs / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)} s`;

    const minutes = Math.floor(seconds / 60);
    const remSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remSeconds}s`;
  }

  function statusClass(status: string): string {
    if (status === 'completed') return 'status completed';
    if (status === 'failed') return 'status failed';
    if (status === 'running') return 'status running';
    if (status === 'cancelled') return 'status cancelled';
    return 'status';
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

  async function loadDashboard() {
    loading = true;
    error = '';

    try {
      const runsParams = new URLSearchParams({ limit: '8', sort_direction: 'desc' });
      if (statusFilter) {
        runsParams.set('status', statusFilter);
      }

      const [metricsRes, runsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/executions/metrics?days=${days}`),
        fetch(`${API_BASE}/api/v1/executions/page?${runsParams.toString()}`),
      ]);

      if (!metricsRes.ok) {
        throw new Error(`Metrics load failed: ${metricsRes.status}`);
      }
      if (!runsRes.ok) {
        throw new Error(`Recent runs load failed: ${runsRes.status}`);
      }

      metrics = await metricsRes.json();
      const runsPayload = await runsRes.json();
      recentRuns = runsPayload.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading = false;
    }
  }

  function loadPrefs() {
    if (typeof window === 'undefined') return;

    try {
      const raw = window.localStorage.getItem(DASHBOARD_PREFS_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        days?: string;
        statusFilter?: '' | 'running' | 'completed' | 'failed' | 'cancelled';
        successAlertThreshold?: string;
      };

      if (parsed.days) days = parsed.days;
      if (parsed.statusFilter !== undefined) statusFilter = parsed.statusFilter;
      if (parsed.successAlertThreshold) successAlertThreshold = parsed.successAlertThreshold;
    } catch {
      // Ignore malformed local storage values.
    }
  }

  function savePrefs() {
    if (typeof window === 'undefined') return;

    const payload = {
      days,
      statusFilter,
      successAlertThreshold,
    };
    window.localStorage.setItem(DASHBOARD_PREFS_KEY, JSON.stringify(payload));
  }

  $: if (prefsReady) savePrefs();

  onMount(async () => {
    loadPrefs();
    prefsReady = true;
    await loadDashboard();
  });
</script>

<section class="card panel">
  <div class="heading">
    <div>
      <h2>Operations Dashboard</h2>
      <p class="muted">Realtime run health snapshot for approvals and automation outcomes.</p>
    </div>
    <div class="toolbar compact">
      <label>
        Window (days)
        <input class="input" bind:value={days} placeholder="30" />
      </label>
      <label>
        Status filter
        <select class="select" bind:value={statusFilter}>
          <option value="">all</option>
          <option value="running">running</option>
          <option value="completed">completed</option>
          <option value="failed">failed</option>
          <option value="cancelled">cancelled</option>
        </select>
      </label>
      <label>
        Alert threshold (%)
        <input class="input" bind:value={successAlertThreshold} placeholder="80" />
      </label>
      <button class="btn" on:click={loadDashboard} disabled={loading}>
        {loading ? 'Refreshing...' : 'Refresh'}
      </button>
      <a class="btn" href="/live-run">Open Live Run Viewer</a>
    </div>
  </div>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  {#if metrics}
    {#if showSuccessAlert}
      <div class="alert warning" role="status">
        Success rate {metrics.success_rate}% is below threshold {parsedSuccessThreshold}%.
      </div>
    {/if}

    <div class="metrics-grid">
      <div class="tile card">
        <p><strong>Total runs</strong></p>
        <p class="big">{metrics.total_runs}</p>
      </div>
      <div class="tile card">
        <p><strong>Success rate</strong></p>
        <p class="big">{metrics.success_rate}%</p>
      </div>
      <div class="tile card">
        <p><strong>Avg duration</strong></p>
        <p class="big">{formatDuration(metrics.avg_duration_ms)}</p>
      </div>
      <div class="tile card">
        <p><strong>Running</strong></p>
        <p class="big">{metrics.running_runs}</p>
      </div>
      <div class="tile card">
        <p><strong>Failed</strong></p>
        <p class="big">{metrics.failed_runs}</p>
      </div>
      <div class="tile card">
        <p><strong>Cancelled</strong></p>
        <p class="big">{metrics.cancelled_runs}</p>
      </div>
    </div>

    <div class="layout">
      <div class="card pane">
        <h3>Failures Trend</h3>
        {#if metrics.failures_by_day.length > 1}
          <svg viewBox="0 0 360 120" role="img" aria-label="Failures trend">
            <polyline
              points={buildFailureTrendPoints(metrics.failures_by_day)}
              fill="none"
              stroke="var(--text)"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        {:else}
          <p class="muted">Not enough failure points for trendline.</p>
        {/if}

        <div class="history-table compact-table">
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
      </div>

      <div class="card pane">
        <h3>Recent Runs</h3>
        {#if recentRuns.length === 0}
          <p class="muted">No run records yet.</p>
        {:else}
          <div class="history-table compact-table">
            <div class="row header run-row">
              <span>ID</span>
              <span>Status</span>
              <span>Duration</span>
              <span>Created</span>
            </div>
            {#each recentRuns as run}
              <a class="row run-row" href={`/live-run?status=${run.run_status}&run_id=${run.id}`}>
                <span>#{run.id}</span>
                <span><span class={statusClass(run.run_status)}>{run.run_status}</span></span>
                <span>{formatDuration(run.duration_ms)}</span>
                <span>{new Date(run.created_at).toLocaleString()}</span>
              </a>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  .panel {
    padding: 20px;
  }

  .heading {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .toolbar.compact {
    display: flex;
    gap: 8px;
    align-items: end;
    flex-wrap: wrap;
  }

  .alert {
    margin-top: 12px;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .alert.warning {
    background: #fff7dd;
    color: #8a6414;
    border-color: #e1dabd;
  }

  .metrics-grid {
    margin-top: 14px;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .tile {
    padding: 10px;
  }

  .tile p {
    margin: 0;
  }

  .big {
    margin-top: 6px;
    font-size: 1.2rem;
    font-weight: 700;
  }

  .layout {
    margin-top: 14px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .pane {
    padding: 12px;
  }

  .history-table {
    display: grid;
    gap: 6px;
    margin-top: 8px;
  }

  .row {
    display: grid;
    gap: 8px;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    color: var(--text);
  }

  .row.header {
    font-weight: 600;
    background: var(--surface-soft);
  }

  .metrics-row {
    grid-template-columns: 1fr 90px;
  }

  .run-row {
    grid-template-columns: 60px 120px 110px 1fr;
    text-decoration: none;
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

  svg {
    width: 100%;
    max-width: 520px;
    height: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface-soft);
  }

  .error {
    color: #b42318;
    margin-top: 10px;
  }

  @media (max-width: 900px) {
    .metrics-grid,
    .layout {
      grid-template-columns: 1fr;
    }

    .metrics-row,
    .run-row {
      grid-template-columns: 1fr;
    }
  }
</style>
