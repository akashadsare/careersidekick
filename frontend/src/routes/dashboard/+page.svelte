<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
  const DASHBOARD_PREFS_KEY = 'careersidekick_dashboard_prefs';
  const CONSECUTIVE_DEGRADATION_THRESHOLD = 3;
  const ALERT_MUTE_MINUTES = 10;
  const INCIDENT_PAGE_SIZE = 20;

  type AlertState = 'normal' | 'warning' | 'critical' | 'muted';

  type IncidentEvent = {
    id?: number;
    state: 'warning' | 'critical' | 'muted' | 'recovered';
    message: string;
    at: string;
    createdAt: string;
  };

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
  let incidentStateFilter: '' | 'warning' | 'critical' | 'muted' | 'recovered' = '';
  let successAlertThreshold = '80';
  let autoRefreshEnabled = false;
  let autoRefreshSeconds = '30';
  let lastUpdatedAt = '';
  let loading = false;
  let error = '';
  let prefsReady = false;
  let refreshTimer: ReturnType<typeof setInterval> | null = null;
  let lowSuccessStreak = 0;
  let mutedUntilEpochMs = 0;
  let previousAlertState: AlertState = 'normal';
  let incidentTimeline: IncidentEvent[] = [];
  let incidentHasMore = false;
  let hiddenFilteredIncidentCount = 0;
  let incidentLoading = false;
  let incidentLoadingMore = false;

  $: parsedSuccessThreshold = Number(successAlertThreshold);
  $: hasValidThreshold = Number.isFinite(parsedSuccessThreshold) && parsedSuccessThreshold >= 0;
  $: showSuccessAlert =
    hasValidThreshold && metrics !== null && metrics.success_rate < parsedSuccessThreshold;
  $: isMuted = mutedUntilEpochMs > Date.now();
  $: showEscalatedAlert =
    showSuccessAlert && lowSuccessStreak >= CONSECUTIVE_DEGRADATION_THRESHOLD && !isMuted;
  $: oldestLoadedIncidentAt =
    incidentTimeline.length > 0
      ? new Date(incidentTimeline[incidentTimeline.length - 1].createdAt).toLocaleString()
      : '';

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

  function computeAlertState(currentMetrics: Metrics | null, streak: number): AlertState {
    if (!hasValidThreshold || currentMetrics === null) return 'normal';
    if (currentMetrics.success_rate >= parsedSuccessThreshold) return 'normal';
    if (mutedUntilEpochMs > Date.now()) return 'muted';
    if (streak >= CONSECUTIVE_DEGRADATION_THRESHOLD) return 'critical';
    return 'warning';
  }

  function appendIncident(event: IncidentEvent) {
    incidentTimeline = [event, ...incidentTimeline].slice(0, 100);
  }

  function incidentMatchesActiveFilters(state: IncidentEvent['state'], createdAt: string): boolean {
    if (incidentStateFilter && state !== incidentStateFilter) {
      return false;
    }

    const windowDays = Number(days);
    if (!Number.isFinite(windowDays) || windowDays < 1) {
      return true;
    }

    const createdAtEpochMs = Date.parse(createdAt);
    if (Number.isNaN(createdAtEpochMs)) {
      return true;
    }

    const windowStartEpochMs = Date.now() - windowDays * 24 * 60 * 60 * 1000;
    return createdAtEpochMs >= windowStartEpochMs;
  }

  function toAlertState(state: IncidentEvent['state']): AlertState {
    if (state === 'critical') return 'critical';
    if (state === 'warning') return 'warning';
    if (state === 'muted') return 'muted';
    return 'normal';
  }

  async function loadIncidents(options: { append?: boolean; cursor?: number | null } = {}) {
    const append = options.append ?? false;
    const cursor = options.cursor ?? null;

    if (append) {
      incidentLoadingMore = true;
    } else {
      incidentLoading = true;
      hiddenFilteredIncidentCount = 0;
    }

    try {
      const params = new URLSearchParams({ limit: String(INCIDENT_PAGE_SIZE) });
      if (days) {
        params.set('days', days);
      }
      if (incidentStateFilter) {
        params.set('state', incidentStateFilter);
      }
      if (cursor !== null) {
        params.set('cursor', String(cursor));
      }

      const response = await fetch(`${API_BASE}/api/v1/executions/incidents?${params.toString()}`);
      if (!response.ok) {
        return;
      }

      const payload = (await response.json()) as Array<{
        id: number;
        state: IncidentEvent['state'];
        message: string;
        created_at: string;
      }>;

      const mapped = payload.map((event) => ({
        id: event.id,
        state: event.state,
        message: event.message,
        at: new Date(event.created_at).toLocaleTimeString(),
        createdAt: event.created_at,
      }));

      incidentHasMore = payload.length === INCIDENT_PAGE_SIZE;

      if (append) {
        incidentTimeline = [...incidentTimeline, ...mapped];
      } else {
        incidentTimeline = mapped;
      }

      if (!append && incidentTimeline.length > 0) {
        previousAlertState = toAlertState(incidentTimeline[0].state);
      }
    } catch {
      // Incident hydration is best-effort and should not block dashboard loading.
    } finally {
      if (append) {
        incidentLoadingMore = false;
      } else {
        incidentLoading = false;
      }
    }
  }

  function loadOlderIncidents() {
    if (!incidentHasMore || incidentLoadingMore) {
      return;
    }

    const oldestIncidentId = incidentTimeline.at(-1)?.id;
    if (oldestIncidentId === undefined) {
      return;
    }

    void loadIncidents({ append: true, cursor: oldestIncidentId });
  }

  function resetIncidentTimeline() {
    void loadIncidents();
  }

  async function persistIncident(state: IncidentEvent['state'], message: string): Promise<void> {
    const response = await fetch(`${API_BASE}/api/v1/executions/incidents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state, message }),
    });

    if (!response.ok) {
      throw new Error('incident persist failed');
    }

    const payload = (await response.json()) as {
      id: number;
      state: IncidentEvent['state'];
      message: string;
      created_at: string;
    };

    if (incidentMatchesActiveFilters(payload.state, payload.created_at)) {
      appendIncident({
        id: payload.id,
        state: payload.state,
        message: payload.message,
        at: new Date(payload.created_at).toLocaleTimeString(),
        createdAt: payload.created_at,
      });
    } else {
      hiddenFilteredIncidentCount += 1;
    }
  }

  async function recordAlertTransition(nextState: AlertState) {
    if (nextState === previousAlertState) return;

    if (nextState === 'normal' && previousAlertState !== 'normal') {
      const message = `Recovered from ${previousAlertState}.`;
      try {
        await persistIncident('recovered', message);
      } catch {
        const now = new Date().toISOString();
        if (incidentMatchesActiveFilters('recovered', now)) {
          appendIncident({ state: 'recovered', message, at: new Date(now).toLocaleTimeString(), createdAt: now });
        } else {
          hiddenFilteredIncidentCount += 1;
        }
      }
      previousAlertState = 'normal';
      return;
    }

    let state: IncidentEvent['state'] | null = null;
    let message = '';

    if (nextState === 'warning') {
      state = 'warning';
      message = 'Success rate dropped below threshold.';
    } else if (nextState === 'critical') {
      state = 'critical';
      message = 'Escalated to sustained degradation.';
    } else if (nextState === 'muted') {
      state = 'muted';
      message = 'Critical alerts are muted.';
    }

    if (state !== null) {
      try {
        await persistIncident(state, message);
      } catch {
        const now = new Date().toISOString();
        if (incidentMatchesActiveFilters(state, now)) {
          appendIncident({ state, message, at: new Date(now).toLocaleTimeString(), createdAt: now });
        } else {
          hiddenFilteredIncidentCount += 1;
        }
      }
    }

    previousAlertState = nextState;
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
      lastUpdatedAt = new Date().toLocaleString();

      await loadIncidents();

      if (hasValidThreshold && metrics && metrics.success_rate < parsedSuccessThreshold) {
        lowSuccessStreak += 1;
      } else {
        lowSuccessStreak = 0;
      }

      const nextState = computeAlertState(metrics, lowSuccessStreak);
      await recordAlertTransition(nextState);
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
        incidentStateFilter?: '' | 'warning' | 'critical' | 'muted' | 'recovered';
        successAlertThreshold?: string;
        autoRefreshEnabled?: boolean;
        autoRefreshSeconds?: string;
        mutedUntilEpochMs?: number;
      };

      if (parsed.days) days = parsed.days;
      if (parsed.statusFilter !== undefined) statusFilter = parsed.statusFilter;
      if (parsed.incidentStateFilter !== undefined) incidentStateFilter = parsed.incidentStateFilter;
      if (parsed.successAlertThreshold) successAlertThreshold = parsed.successAlertThreshold;
      if (typeof parsed.autoRefreshEnabled === 'boolean') autoRefreshEnabled = parsed.autoRefreshEnabled;
      if (parsed.autoRefreshSeconds) autoRefreshSeconds = parsed.autoRefreshSeconds;
      if (typeof parsed.mutedUntilEpochMs === 'number') mutedUntilEpochMs = parsed.mutedUntilEpochMs;
    } catch {
      // Ignore malformed local storage values.
    }
  }

  function savePrefs() {
    if (typeof window === 'undefined') return;

    const payload = {
      days,
      statusFilter,
      incidentStateFilter,
      successAlertThreshold,
      autoRefreshEnabled,
      autoRefreshSeconds,
      mutedUntilEpochMs,
    };
    window.localStorage.setItem(DASHBOARD_PREFS_KEY, JSON.stringify(payload));
  }

  function muteAlertsForTenMinutes() {
    mutedUntilEpochMs = Date.now() + ALERT_MUTE_MINUTES * 60 * 1000;
    void recordAlertTransition('muted');
  }

  function clearAutoRefreshTimer() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  function restartAutoRefreshTimer() {
    if (typeof window === 'undefined') return;

    clearAutoRefreshTimer();

    if (!autoRefreshEnabled) return;

    const seconds = Number(autoRefreshSeconds);
    if (!Number.isFinite(seconds) || seconds < 5) return;

    refreshTimer = setInterval(() => {
      void loadDashboard();
    }, seconds * 1000);
  }

  $: if (prefsReady) savePrefs();
  $: if (prefsReady) restartAutoRefreshTimer();

  onMount(async () => {
    loadPrefs();
    prefsReady = true;
    await loadDashboard();
  });

  onDestroy(() => {
    clearAutoRefreshTimer();
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
        Incident state
        <select class="select" bind:value={incidentStateFilter}>
          <option value="">all</option>
          <option value="warning">warning</option>
          <option value="critical">critical</option>
          <option value="muted">muted</option>
          <option value="recovered">recovered</option>
        </select>
      </label>
      <label>
        Alert threshold (%)
        <input class="input" bind:value={successAlertThreshold} placeholder="80" />
      </label>
      <label>
        <input type="checkbox" bind:checked={autoRefreshEnabled} />
        Auto refresh
      </label>
      <label>
        Refresh every
        <select class="select" bind:value={autoRefreshSeconds} disabled={!autoRefreshEnabled}>
          <option value="15">15s</option>
          <option value="30">30s</option>
          <option value="60">60s</option>
        </select>
      </label>
      <button class="btn" on:click={loadDashboard} disabled={loading}>
        {loading ? 'Refreshing...' : 'Refresh'}
      </button>
      <a class="btn" href="/live-run">Open Live Run Viewer</a>
    </div>
  </div>

  {#if lastUpdatedAt}
    <p class="muted">Last updated: {lastUpdatedAt}</p>
  {/if}

  {#if error}
    <p class="error">{error}</p>
  {/if}

  {#if metrics}
    {#if showSuccessAlert}
      <div class="alert warning" role="status">
        Success rate {metrics.success_rate}% is below threshold {parsedSuccessThreshold}%.
        {#if lowSuccessStreak > 1}
          ({lowSuccessStreak} consecutive windows)
        {/if}
      </div>
    {/if}

    {#if showEscalatedAlert}
      <div class="alert critical" role="alert">
        Sustained degradation detected ({lowSuccessStreak} consecutive windows below threshold).
        <button class="btn" on:click={muteAlertsForTenMinutes}>Mute for 10 minutes</button>
      </div>
    {:else if isMuted && showSuccessAlert}
      <p class="muted">Critical degradation alerts are muted until {new Date(mutedUntilEpochMs).toLocaleTimeString()}.</p>
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
        <h3>Incident Timeline</h3>
        {#if hiddenFilteredIncidentCount > 0}
          <p class="muted incident-note" role="status">
            {hiddenFilteredIncidentCount}
            {hiddenFilteredIncidentCount === 1 ? ' new incident is' : ' new incidents are'} hidden by the current timeline filters.
          </p>
        {/if}
        {#if incidentLoading && incidentTimeline.length === 0}
          <div class="timeline-list" aria-label="Incident timeline loading">
            {#each Array.from({ length: 3 }) as _, index}
              <div class="timeline-row skeleton" aria-hidden="true" data-skeleton-row={index}>
                <span class="skeleton-chip"></span>
                <span class="skeleton-chip"></span>
                <span class="skeleton-line"></span>
              </div>
            {/each}
          </div>
        {:else if incidentTimeline.length === 0}
          <p class="muted">No alert transitions yet.</p>
        {:else}
          <div class="timeline-list">
            {#each incidentTimeline as event}
              <div class="timeline-row">
                <span class="timeline-time">{event.at}</span>
                <span class="timeline-state {event.state}">{event.state}</span>
                <span>{event.message}</span>
              </div>
            {/each}
          </div>

          {#if incidentHasMore}
            <button class="btn" on:click={loadOlderIncidents} disabled={incidentLoadingMore}>
              {incidentLoadingMore ? 'Loading...' : 'Load older incidents'}
            </button>
          {/if}

          {#if incidentTimeline.length > INCIDENT_PAGE_SIZE}
            <button class="btn" on:click={resetIncidentTimeline}>Reset timeline</button>
          {/if}

          <p class="muted timeline-footer">
            Showing {incidentTimeline.length} incidents
            {#if oldestLoadedIncidentAt}
              · Oldest loaded: {oldestLoadedIncidentAt}
            {/if}
          </p>
        {/if}
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

  .toolbar.compact label input[type='checkbox'] {
    margin-right: 6px;
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

  .alert.critical {
    margin-top: 8px;
    background: #fde8e8;
    color: #a01818;
    border-color: #f4b8b8;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }

  .timeline-list {
    display: grid;
    gap: 8px;
    margin-top: 8px;
  }

  .timeline-row {
    display: grid;
    grid-template-columns: 88px 92px 1fr;
    gap: 8px;
    align-items: center;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface-soft);
    font-size: 13px;
  }

  .timeline-footer {
    margin-top: 10px;
    font-size: 12px;
  }

  .incident-note {
    margin: 8px 0 10px;
    color: #8a6414;
  }

  .timeline-row.skeleton {
    grid-template-columns: 88px 92px 1fr;
  }

  .skeleton-chip,
  .skeleton-line {
    display: inline-block;
    height: 14px;
    border-radius: 999px;
    background: linear-gradient(90deg, #ececec 0%, #f5f5f5 50%, #ececec 100%);
    background-size: 200% 100%;
    animation: timeline-shimmer 1.1s linear infinite;
  }

  .skeleton-chip {
    width: 72px;
  }

  .skeleton-line {
    width: 100%;
  }

  @keyframes timeline-shimmer {
    from {
      background-position: 200% 0;
    }
    to {
      background-position: -200% 0;
    }
  }

  .timeline-time {
    color: var(--muted);
  }

  .timeline-state {
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.02em;
    font-weight: 700;
    padding: 2px 6px;
    border: 1px solid var(--border);
    border-radius: 999px;
    width: fit-content;
  }

  .timeline-state.warning {
    background: #fff7dd;
    color: #8a6414;
  }

  .timeline-state.critical {
    background: #fde8e8;
    color: #a01818;
  }

  .timeline-state.muted {
    background: #ececec;
    color: #4b4b4b;
  }

  .timeline-state.recovered {
    background: #e8f6e8;
    color: #1f6b36;
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
    grid-template-columns: 1fr 1fr 1fr;
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

    .timeline-row {
      grid-template-columns: 1fr;
    }
  }
</style>
