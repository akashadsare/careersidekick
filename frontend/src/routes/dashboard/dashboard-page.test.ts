import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardPage from './+page.svelte';

describe('DashboardPage', () => {
  beforeEach(() => {
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
});
