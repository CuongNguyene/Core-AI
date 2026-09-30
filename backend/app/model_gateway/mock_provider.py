from app.model_gateway.errors import ProviderResponseError
from app.model_gateway.providers import ProviderRequest, ProviderResponse


class MockProvider:
    """In-memory provider for gateway tests; it never performs HTTP."""

    is_external = False

    def __init__(self, provider_id: str, model: str, responses: list[str]) -> None:
        self.provider_id = provider_id
        self._model = model
        self._responses = list(responses)
        self.call_count = 0
        self.requests: list[ProviderRequest] = []

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.call_count += 1
        self.requests.append(request)
        if not self._responses:
            raise ProviderResponseError("Mock provider has no configured response")
        return ProviderResponse(
            provider=self.provider_id,
            model=self._model,
            content=self._responses.pop(0),
            latency_ms=0,
        )
