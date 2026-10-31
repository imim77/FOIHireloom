from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://myuser:mypassword@localhost:5432/myapp"
    )
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0)

    CKAN_BASE_URL: str = "https://data.gov.hr/ckan"
    CKAN_DATASET_ID: str = Field(
        default="slobodna-radna-mjesta-po-zupanijama-u-rh-i-eu", min_length=1
    )
    CKAN_OCCUPATION_DATASET_ID: str = Field(default="slobodna-radna-mjesta-po-zanimanju", min_length=1)
    CKAN_TIMEOUT: float = Field(default=15.0, gt=0, allow_inf_nan=False)

    HZZ_FEED_TIMEOUT: float = Field(default=15.0, gt=0, allow_inf_nan=False)
    HZZ_FEED_MAX_BYTES: int = Field(default=5 * 1024 * 1024, gt=0)
    HZZ_MIN_RETAINED_RATIO: float = Field(default=0.5, ge=0, le=1)
    # Explicit job categories that must agree before an occupation feed's
    # category may fill in jobs without one.
    HZZ_OCCUPATION_MIN_EXAMPLES: int = Field(default=3, ge=1)
    HZZ_STALE_AFTER_HOURS: float = Field(default=6.0, gt=0, allow_inf_nan=False)

    HZZ_PAGE_TIMEOUT: float = Field(default=15.0, gt=0, allow_inf_nan=False)
    HZZ_PAGE_MAX_BYTES: int = Field(default=2 * 1024 * 1024, gt=0)
    HZZ_PAGE_DELAY_SECONDS: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    HZZ_PAGE_BATCH_SIZE: int = Field(default=500, ge=1)
    HZZ_PAGE_RETRY_HOURS: float = Field(default=24.0, gt=0, allow_inf_nan=False)
    HZZ_PAGE_MAX_CONSECUTIVE_FAILURES: int = Field(default=5, ge=1)

    MCP_TRANSPORT: Literal["stdio", "http"] = "stdio"
    MCP_HOST: str = Field(default="127.0.0.1", min_length=1)
    MCP_PORT: int = Field(default=8000, ge=1, le=65535)
    MCP_PATH: str = Field(default="/mcp", pattern=r"^/[^\s]*$")
    # Host names, besides localhost, that clients may use to reach the HTTP
    # server, e.g. a tunnel or proxy domain. Comma-separated in the environment.
    MCP_ALLOWED_HOSTS: Annotated[list[str], NoDecode] = []

    @field_validator("MCP_ALLOWED_HOSTS", mode="before")
    @classmethod
    def split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value
