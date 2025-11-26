"""Official Consultaion API client for Python."""

import json
from typing import AsyncIterator, Callable, Optional

import httpx

from .types import Debate, DebateCreateOptions, DebateEvent


class ConsultaionClient:
    """Official Consultaion API client.
    
    Example:
        >>> client = ConsultaionClient(
        ...     base_url="https://api.consultaion.com",
        ...     api_key="your-api-key"
        ... )
        >>> debate = await client.create_debate({
        ...     "prompt": "What are the pros and cons of remote work?",
        ...     "routing_policy": "router-smart"
        ... })
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        **httpx_kwargs: any,
    ) -> None:
        """Initialize the Consultaion client.
        
        Args:
            base_url: Base URL for the API (e.g., 'https://api.consultaion.com')
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds (default: 30.0)
            **httpx_kwargs: Additional arguments to pass to httpx.AsyncClient
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            **httpx_kwargs,
        )

    async def __aenter__(self) -> "ConsultaionClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def create_debate(self, options: DebateCreateOptions) -> Debate:
        """Create a new debate.
        
        Args:
            options: Debate creation options
            
        Returns:
            The created Debate object
            
        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = await self._client.post(
            "/debates",
            json=options,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_debate(self, debate_id: str) -> Debate:
        """Get a debate by ID.
        
        Args:
            debate_id: The debate ID
            
        Returns:
            The Debate object
            
        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = await self._client.get(
            f"/debates/{debate_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def stream_events(
        self, debate_id: str
    ) -> AsyncIterator[DebateEvent]:
        """Stream Server-Sent Events from a debate.
        
        Args:
            debate_id: The debate ID
            
        Yields:
            DebateEvent objects as they arrive
            
        Example:
            >>> async for event in client.stream_events(debate.id):
            ...     print(f"Event: {event['type']}")
        """
        async with self._client.stream(
            "GET",
            f"/debates/{debate_id}/stream",
            headers=self._get_headers(),
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield {"type": "message", "data": data}
                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        continue
