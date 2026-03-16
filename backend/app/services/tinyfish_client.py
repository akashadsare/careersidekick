import json
from collections.abc import AsyncIterator

import httpx

from ..config import settings


async def stream_tinyfish_sse(payload: dict) -> AsyncIterator[str]:
    headers = {
        'Content-Type': 'application/json',
    }
    if settings.tinyfish_api_key:
        headers['X-API-Key'] = settings.tinyfish_api_key

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            'POST',
            settings.tinyfish_api_url,
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                text = await response.aread()
                err = {
                    'type': 'COMPLETE',
                    'status': 'FAILED',
                    'error': {
                        'message': f'TinyFish API error {response.status_code}: {text.decode("utf-8", errors="ignore")}',
                    },
                }
                yield f'data: {json.dumps(err)}\n\n'
                return

            async for line in response.aiter_lines():
                if not line:
                    continue
                # Forward TinyFish SSE lines as-is.
                yield f'{line}\n'
