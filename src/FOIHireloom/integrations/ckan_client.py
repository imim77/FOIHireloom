import math
from uuid import UUID

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, ValidationError


class CkanError(RuntimeError):
    """A CKAN request could not supply valid dataset resources."""


class CkanTransportError(CkanError):
    """The HTTP request failed, including timeouts."""


class CkanHttpError(CkanError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"CKAN returned HTTP {status_code}.")


class CkanApiError(CkanError):
    """CKAN returned success=false, even if HTTP succeeded."""


class CkanResponseError(CkanError):
    """The response is not a valid package_show response."""


class CkanResource(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: UUID
    url: AnyHttpUrl
    name: str | None = None
    description: str | None = None
    format: str | None = None
    state: str | None = "active"


class _CkanPackage(BaseModel):
    resources: list[CkanResource]


class CkanClient:
    """Read CKAN metadata using a caller-owned async HTTP client.

    This client neither filters counties nor downloads RSS contents. The caller
    closes the injected httpx.AsyncClient, normally with an async context.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str = "https://data.gov.hr/ckan",
        timeout: float = 15.0,
    ) -> None:
        url = httpx.URL(base_url)
        if url.scheme not in {"http", "https"} or not url.host or url.query or url.fragment:
            raise ValueError("CKAN base URL must be an HTTP(S) URL without query or fragment.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("CKAN timeout must be positive and finite.")
        self._client = client
        self._url = f"{str(url).rstrip('/')}/api/3/action/package_show"
        self._timeout = timeout

    async def get_resources(self, dataset_id: str) -> list[CkanResource]:
        if not dataset_id.strip():
            raise ValueError("CKAN dataset ID must not be blank.")
        try:
            response = await self._client.get(
                self._url, params={"id": dataset_id}, timeout=self._timeout,
                follow_redirects=True,
            )
        except httpx.RequestError as error:
            raise CkanTransportError("Could not reach the CKAN API.") from error
        if not response.is_success:
            raise CkanHttpError(response.status_code)
        try:
            payload = response.json()
        except ValueError as error:
            raise CkanResponseError("CKAN did not return valid JSON.") from error
        if not isinstance(payload, dict) or type(payload.get("success")) is not bool:
            raise CkanResponseError("CKAN response must contain a boolean success field.")
        if payload["success"] is False:
            raise CkanApiError("CKAN reported an unsuccessful package_show response.")
        try:
            return _CkanPackage.model_validate(payload.get("result")).resources
        except ValidationError as error:
            raise CkanResponseError("CKAN returned invalid dataset resources.") from error
