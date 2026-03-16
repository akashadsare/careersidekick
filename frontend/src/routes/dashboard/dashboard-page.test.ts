import { fireEvent, render, screen } from '@testing-library/svelte';
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
    const select = screen.getByRole('combobox');
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
        successAlertThreshold: '90',
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
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(DashboardPage);

    await screen.findByText('Success rate 50% is below threshold 90%.');

    const allUrls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(allUrls.some((url) => url.includes('/api/v1/executions/metrics?days=14'))).toBe(true);
    expect(allUrls.some((url) => url.includes('/api/v1/executions/page?') && url.includes('status=running'))).toBe(true);
  });
});
