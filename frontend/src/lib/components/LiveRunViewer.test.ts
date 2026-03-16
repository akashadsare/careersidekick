import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LiveRunViewer from './LiveRunViewer.svelte';

describe('LiveRunViewer', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders pagination total count and formats durations in history and details', async () => {
    const pagePayload = {
      data: [
        {
          id: 1,
          draft_id: 7,
          tinyfish_run_id: 'tf-1',
          run_status: 'completed',
          started_at: '2026-03-16T08:00:00Z',
          finished_at: '2026-03-16T08:00:01.250Z',
          duration_ms: 1250,
          streaming_url: null,
          error_message: null,
          created_at: '2026-03-16T08:00:00Z',
        },
      ],
      pagination: {
        limit: 25,
        cursor: null,
        next_cursor: null,
        has_more: false,
        total_count: 42,
        sort_direction: 'desc',
      },
    };

    const detailPayload = {
      ...pagePayload.data[0],
      duration_ms: 65000,
      result_json: { ok: true },
    };

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          json: async () => pagePayload,
          status: 200,
        } as Response;
      }

      if (url.includes('/api/v1/executions/1')) {
        return {
          ok: true,
          json: async () => detailPayload,
          status: 200,
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(LiveRunViewer);

    await screen.findByText(/Total:\s*42/);
    expect(screen.getByText('1.3 s')).toBeTruthy();

    const runButton = screen.getByRole('button', { name: /tf-1/i });
    await fireEvent.click(runButton);

    await screen.findByText('1m 5s');
    expect(screen.getByText('1m 5s')).toBeTruthy();
  });

  it('rolls back optimistic status update when API update fails', async () => {
    const pagePayload = {
      data: [
        {
          id: 9,
          draft_id: 3,
          tinyfish_run_id: 'tf-9',
          run_status: 'completed',
          started_at: '2026-03-16T08:00:00Z',
          finished_at: '2026-03-16T08:00:02.000Z',
          duration_ms: 2000,
          streaming_url: null,
          error_message: null,
          created_at: '2026-03-16T08:00:00Z',
        },
      ],
      pagination: {
        limit: 25,
        cursor: null,
        next_cursor: null,
        has_more: false,
        total_count: 1,
        sort_direction: 'desc',
      },
    };

    const detailPayload = {
      ...pagePayload.data[0],
      result_json: { ok: true },
    };

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/page')) {
        return {
          ok: true,
          json: async () => pagePayload,
          status: 200,
        } as Response;
      }

      if (url.endsWith('/api/v1/executions/9') && (!init || init.method === 'GET')) {
        return {
          ok: true,
          json: async () => detailPayload,
          status: 200,
        } as Response;
      }

      if (url.endsWith('/api/v1/executions/9/status') && init?.method === 'PATCH') {
        return {
          ok: false,
          status: 500,
          json: async () => ({}),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(LiveRunViewer);

    const runButton = await screen.findByRole('button', { name: /tf-9/i });
    expect(runButton.textContent).toContain('completed');

    await fireEvent.click(runButton);
    await screen.findByText(/Run 9/);

    const setFailedButton = screen.getByRole('button', { name: 'Set failed' });
    await fireEvent.click(setFailedButton);

    await screen.findByText('Status update failed: 500');
    expect(runButton.textContent).toContain('completed');
  });

  it('keeps updated status after successful PATCH and refreshes detail/history', async () => {
    const runningRow = {
      id: 14,
      draft_id: 4,
      tinyfish_run_id: 'tf-14',
      run_status: 'running',
      started_at: '2026-03-16T08:00:00Z',
      finished_at: null,
      duration_ms: null,
      streaming_url: null,
      error_message: null,
      created_at: '2026-03-16T08:00:00Z',
    };

    const completedRow = {
      ...runningRow,
      run_status: 'completed',
      finished_at: '2026-03-16T08:00:03.000Z',
      duration_ms: 3000,
    };

    let pageCalls = 0;

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.includes('/api/v1/executions/page')) {
        pageCalls += 1;
        const data = pageCalls === 1 ? [runningRow] : [completedRow];
        return {
          ok: true,
          json: async () => ({
            data,
            pagination: {
              limit: 25,
              cursor: null,
              next_cursor: null,
              has_more: false,
              total_count: 1,
              sort_direction: 'desc',
            },
          }),
          status: 200,
        } as Response;
      }

      if (url.endsWith('/api/v1/executions/14') && (!init || init.method === 'GET')) {
        const detail = pageCalls <= 1 ? { ...runningRow, result_json: null } : { ...completedRow, result_json: { ok: true } };
        return {
          ok: true,
          json: async () => detail,
          status: 200,
        } as Response;
      }

      if (url.endsWith('/api/v1/executions/14/status') && init?.method === 'PATCH') {
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: 14, run_status: 'completed' }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response;
    });

    vi.stubGlobal('fetch', fetchMock);

    render(LiveRunViewer);

    const runButton = await screen.findByRole('button', { name: /tf-14/i });
    expect(runButton.textContent).toContain('running');

    await fireEvent.click(runButton);
    await screen.findByText(/Run 14/);

    const setCompletedButton = screen.getByRole('button', { name: 'Set completed' });
    await fireEvent.click(setCompletedButton);

    await screen.findByText('3.0 s');
    expect(runButton.textContent).toContain('completed');
    expect(screen.queryByText('Status update failed: 500')).toBeNull();
  });
});
