import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardPage from './+page.svelte';

describe('DashboardPage', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders metrics and recent runs', async () => {
    const metricsPayload = {
      window_days: 30,
      total_runs: 12,
      completed_runs: 8,
      failed_runs: 2,
      cancelled_runs: 1,
      running_runs: 1,
      success_rate: 66.67,
      avg_duration_ms: 2450,
      failures_by_day: [
        { day: '2026-03-15', count: 1 },
        { day: '2026-03-16', count: 2 },
      ],
    };

    const runsPayload = {
      data: [
        {
          id: 101,
          draft_id: 12,
          run_status: 'completed',
          duration_ms: 1800,
          tinyfish_run_id: 'tf-101',
          created_at: '2026-03-16T10:00:00Z',
        },
      ],
      pagination: {
        limit: 8,
        cursor: null,
        next_cursor: null,
        has_more: false,
        total_count: 1,
        sort_direction: 'desc',
      },
    };

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => metricsPayload,
        } as Response;
      }

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => runsPayload,
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Operations Dashboard');
    await screen.findByText('66.67%');
    await screen.findByText('#101');
    await screen.findByText('Failures Trend');
    await screen.findByText('Success rate 66.67% is below threshold 80%.');
  });

  it('applies selected status filter when refreshing recent runs', async () => {
    const metricsPayload = {
      window_days: 30,
      total_runs: 4,
      completed_runs: 3,
      failed_runs: 1,
      cancelled_runs: 0,
      running_runs: 0,
      success_rate: 75,
      avg_duration_ms: 2000,
      failures_by_day: [{ day: '2026-03-16', count: 1 }],
    };

    const runsPayload = {
      data: [],
      pagination: {
        limit: 8,
        cursor: null,
        next_cursor: null,
        has_more: false,
        total_count: 0,
        sort_direction: 'desc',
      },
    };

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => metricsPayload,
        } as Response;
      }

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => runsPayload,
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Operations Dashboard');
    const select = screen.getByRole('combobox', { name: 'Status filter' });
    await fireEvent.change(select, { target: { value: 'failed' } });

    const refreshButton = await screen.findByRole('button', { name: 'Refresh' });
    await fireEvent.click(refreshButton);

    const pageCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/page'));
    expect(pageCalls.some((url) => url.includes('status=failed'))).toBe(true);
  });

  it('renders error message when metrics request fails', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: false,
          status: 500,
          json: async () => ({}),
        } as Response;
      }

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Metrics load failed: 500');
  });

  it('restores persisted dashboard preferences from localStorage', async () => {
    localStorage.setItem(
      'careersidekick_dashboard_prefs',
      JSON.stringify({
        days: '14',
        statusFilter: 'running',
        incidentStateFilter: 'critical',
        successAlertThreshold: '90',
        autoRefreshEnabled: true,
        autoRefreshSeconds: '15',
      }),
    );

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 14,
            total_runs: 2,
            completed_runs: 1,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 50,
            avg_duration_ms: 1200,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/incidents')) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Success rate 50% is below threshold 90%.');
    await screen.findByText('No incidents match the current timeline filters.');
    await screen.findByText('14d window');
    await screen.findByText('state: critical');

    const autoRefreshCheckbox = screen.getByRole('checkbox');
    expect(autoRefreshCheckbox).toBeTruthy();
    expect((autoRefreshCheckbox as HTMLInputElement).checked).toBe(true);

    const selects = screen.getAllByRole('combobox');
    const intervalSelect = selects[2] as HTMLSelectElement;
    expect(intervalSelect.value).toBe('15');

    const allUrls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(allUrls.some((url) => url.includes('/api/v1/executions/metrics?days=14'))).toBe(true);
    expect(allUrls.some((url) => url.includes('/api/v1/executions/page?') && url.includes('status=running'))).toBe(true);
    expect(
      allUrls.some(
        (url) =>
          url.includes('/api/v1/executions/incidents?') &&
          url.includes('days=14') &&
          url.includes('state=critical'),
      ),
    ).toBe(true);
  });

  it('clears incident state filter from the header chip', async () => {
    localStorage.setItem(
      'careersidekick_dashboard_prefs',
      JSON.stringify({
        days: '14',
        incidentStateFilter: 'critical',
      }),
    );

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 14,
            total_runs: 2,
            completed_runs: 2,
            failed_runs: 0,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 100,
            avg_duration_ms: 1200,
            failures_by_day: [],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/incidents')) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    const clearChipButton = await screen.findByRole('button', { name: /Clear incident state filter/ });
    await fireEvent.click(clearChipButton);

    await waitFor(() => {
      expect(screen.queryByText('state: critical')).toBeNull();
    });

    const incidentCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/incidents?'));
    expect(incidentCalls.some((url) => url.includes('state=critical'))).toBe(true);
    expect(incidentCalls.some((url) => url.includes('days=14') && !url.includes('state='))).toBe(true);
  });

  it('resets the window chip back to the default 30-day scope', async () => {
    localStorage.setItem(
      'careersidekick_dashboard_prefs',
      JSON.stringify({
        days: '14',
      }),
    );

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/metrics')) {
        const windowDays = url.includes('days=14') ? 14 : 30;
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: windowDays,
            total_runs: 2,
            completed_runs: 2,
            failed_runs: 0,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 100,
            avg_duration_ms: 1200,
            failures_by_day: [],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/incidents')) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    const resetWindowButton = await screen.findByRole('button', { name: /Reset incident window to default/ });
    await fireEvent.click(resetWindowButton);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Reset incident window to default/ })).toBeNull();
    });
    await screen.findByText('30d window');

    const metricCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/metrics?days='));
    expect(metricCalls.some((url) => url.includes('days=14'))).toBe(true);
    expect(metricCalls.some((url) => url.includes('days=30'))).toBe(true);

    const incidentCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/incidents?'));
    expect(incidentCalls.some((url) => url.includes('days=14'))).toBe(true);
    expect(incidentCalls.some((url) => url.includes('days=30'))).toBe(true);
  });

  it('escalates on sustained degradation and allows muting critical alert', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 6,
            failed_runs: 4,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 60,
            avg_duration_ms: 1600,
            failures_by_day: [{ day: '2026-03-16', count: 4 }],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    const refreshButton = await screen.findByRole('button', { name: 'Refresh' });
    await fireEvent.click(refreshButton);
    await fireEvent.click(refreshButton);

    await screen.findByText(/Sustained degradation detected/);

    const muteButton = screen.getByRole('button', { name: 'Mute for 10 minutes' });
    await fireEvent.click(muteButton);

    await screen.findByText(/Critical degradation alerts are muted until/);
  });

  it('hydrates incident timeline from backend incidents endpoint', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/incidents')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: 7,
              state: 'critical',
              message: 'Escalated to sustained degradation.',
              created_at: '2026-03-16T09:00:00Z',
            },
          ],
        } as Response;
      }
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 9,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 90,
            avg_duration_ms: 2000,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Incident Timeline');
    await screen.findByText('Escalated to sustained degradation.');
  });

  it('passes incident state filter on refresh', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/incidents')) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 9,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 90,
            avg_duration_ms: 2000,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Operations Dashboard');
    const incidentSelect = screen.getByRole('combobox', { name: 'Incident state' });
    await fireEvent.change(incidentSelect, { target: { value: 'muted' } });

    const refreshButton = screen.getByRole('button', { name: /Refresh|Refreshing.../ });
    await waitFor(() => {
      expect((refreshButton as HTMLButtonElement).disabled).toBe(false);
    });
    await fireEvent.click(refreshButton);

    const incidentCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/incidents?'));
    expect(incidentCalls.some((url) => url.includes('state=muted'))).toBe(true);
  });

  it('loads older incidents using cursor pagination', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/incidents')) {
        if (url.includes('cursor=')) {
          return {
            ok: true,
            status: 200,
            json: async () => [
              {
                id: 20,
                state: 'warning',
                message: 'Incident 20',
                created_at: '2026-03-16T08:00:00Z',
              },
            ],
          } as Response;
        }

        const firstPage = Array.from({ length: 20 }, (_, idx) => {
          const id = 40 - idx;
          return {
            id,
            state: 'warning',
            message: `Incident ${id}`,
            created_at: '2026-03-16T09:00:00Z',
          };
        });

        return {
          ok: true,
          status: 200,
          json: async () => firstPage,
        } as Response;
      }
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 9,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 90,
            avg_duration_ms: 2000,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Incident Timeline');
    const loadOlderButton = await screen.findByRole('button', { name: 'Load older incidents' });
    await fireEvent.click(loadOlderButton);

    await screen.findByText('Incident 20');
    await screen.findByText(/Showing/);
    await screen.findByText(/Oldest loaded:/);

    const resetButton = await screen.findByRole('button', { name: 'Reset timeline' });
    await fireEvent.click(resetButton);

    await waitFor(() => {
      expect(screen.queryByText('Incident 20')).toBeNull();
    });

    const incidentCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/incidents?'));
    expect(incidentCalls.some((url) => url.includes('cursor=21'))).toBe(true);
  });

  it('shows incident skeleton while incidents are loading', async () => {
    let resolveIncidents: () => void = () => {};
    const incidentsPromise = new Promise<void>((resolve) => {
      resolveIncidents = resolve;
    });

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/executions/incidents')) {
        await incidentsPromise;
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 9,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 90,
            avg_duration_ms: 2000,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }
      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByLabelText('Incident timeline loading');
    resolveIncidents();

    await waitFor(() => {
      expect(screen.queryByLabelText('Incident timeline loading')).toBeNull();
    });
  });

  it('does not append optimistic incidents that are excluded by active incident filter', async () => {
    localStorage.setItem(
      'careersidekick_dashboard_prefs',
      JSON.stringify({
        days: '30',
        incidentStateFilter: 'critical',
        successAlertThreshold: '95',
      }),
    );

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/incidents') && init?.method === 'POST') {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: 999,
            state: 'warning',
            message: 'Success rate dropped below threshold.',
            created_at: '2026-03-16T10:00:00Z',
          }),
        } as Response;
      }

      if (url.includes('/api/v1/executions/incidents')) {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }

      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 9,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 90,
            avg_duration_ms: 2000,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Operations Dashboard');
    await screen.findByText(/Success rate 90% is below threshold 95%/);
    await screen.findByText(/1 new incident is hidden by the current timeline filters/);
    await waitFor(() => {
      expect(screen.queryByText('Success rate dropped below threshold.')).toBeNull();
    });
  });

  it('can clear the incident state filter from the hidden-incidents note', async () => {
    localStorage.setItem(
      'careersidekick_dashboard_prefs',
      JSON.stringify({
        days: '30',
        incidentStateFilter: 'critical',
        successAlertThreshold: '95',
      }),
    );

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/incidents') && init?.method === 'POST') {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: 999,
            state: 'warning',
            message: 'Success rate dropped below threshold.',
            created_at: '2026-03-16T10:00:00Z',
          }),
        } as Response;
      }

      if (url.includes('/api/v1/executions/incidents')) {
        if (url.includes('state=critical')) {
          return {
            ok: true,
            status: 200,
            json: async () => [],
          } as Response;
        }

        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: 999,
              state: 'warning',
              message: 'Success rate dropped below threshold.',
              created_at: '2026-03-16T10:00:00Z',
            },
          ],
        } as Response;
      }

      if (url.includes('/api/v1/executions/metrics')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            window_days: 30,
            total_runs: 10,
            completed_runs: 9,
            failed_runs: 1,
            cancelled_runs: 0,
            running_runs: 0,
            success_rate: 90,
            avg_duration_ms: 2000,
            failures_by_day: [{ day: '2026-03-16', count: 1 }],
          }),
        } as Response;
      }

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [],
            pagination: {
              limit: 8,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 0,
              sort_direction: 'desc',
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    const noteButton = await screen.findByRole('button', { name: 'Show hidden incidents' });
    await fireEvent.click(noteButton);

    await screen.findByText('Success rate dropped below threshold.');
    await waitFor(() => {
      expect(screen.queryByText(/hidden by the current timeline filters/)).toBeNull();
    });

    const incidentCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/api/v1/executions/incidents?'));
    expect(incidentCalls.some((url) => !url.includes('state='))).toBe(true);
  });
});
