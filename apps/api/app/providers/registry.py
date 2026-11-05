from urllib.parse import quote

import httpx

PROVIDER_ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "xai": "https://api.x.ai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


class ProviderValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def validate_provider_key(provider: str, api_key: str, model: str) -> None:
    if provider not in PROVIDER_ENDPOINTS:
        raise ProviderValidationError("Unsupported provider")
    model_path = quote(model.removeprefix("models/"), safe="")
    base = PROVIDER_ENDPOINTS[provider]
    headers = {}
    if provider in {"openai", "xai"}:
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["x-goog-api-key"] = api_key

    url = f"{base}/models"
    if provider in {"openai", "anthropic", "gemini"}:
        url = f"{base}/models/{model_path}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0)) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise ProviderValidationError("Provider validation timed out. Try again.", 504) from exc
    except httpx.RequestError as exc:
        raise ProviderValidationError("Could not reach the provider. Try again.", 502) from exc

    if response.status_code in {401, 403}:
        raise ProviderValidationError("The provider rejected this API key.", 401)
    if response.status_code == 404:
        raise ProviderValidationError("The selected model was not found for this provider.", 404)
    if response.status_code == 429:
        raise ProviderValidationError("The provider rate-limited validation. Try again shortly.", 429)
    if response.status_code >= 500:
        raise ProviderValidationError("The provider is temporarily unavailable.", 502)
    if response.is_error:
        raise ProviderValidationError("The provider could not validate this key and model.", 400)

    if provider == "xai":
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderValidationError("The provider returned an invalid response.", 502) from exc
        available = payload.get("data") or payload.get("models") or []
        model_ids = {item.get("id") for item in available if isinstance(item, dict)}
        if model not in model_ids:
            raise ProviderValidationError("The selected model is not available for this xAI key.", 404)
