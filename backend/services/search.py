from __future__ import annotations

from typing import Any

import httpx

from backend.config import get_settings


class SearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.searxng_base_url
        self.timeout = settings.searxng_timeout_seconds

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.base_url:
            return [
                {
                    'title': f'No external search configured for: {query}',
                    'url': '',
                    'snippet': 'Set SEARXNG_BASE_URL to use a SearXNG sidecar.',
                    'source': 'local_stub',
                }
            ]
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f'{self.base_url.rstrip("/")}/search',
                params={'q': query, 'format': 'json'},
            )
            response.raise_for_status()
            payload = response.json()
        results = []
        for item in payload.get('results', [])[:limit]:
            results.append(
                {
                    'title': item.get('title', ''),
                    'url': item.get('url', ''),
                    'snippet': item.get('content', ''),
                    'source': item.get('engine', 'searxng'),
                }
            )
        return results


search_service = SearchService()
