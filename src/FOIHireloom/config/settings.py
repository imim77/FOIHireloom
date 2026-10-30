from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    CKAN_TIMEOUT: float = Field(default=15.0, gt=0, allow_inf_nan=False)

    HZZ_FEED_TIMEOUT: float = Field(default=15.0, gt=0, allow_inf_nan=False)
    HZZ_FEED_MAX_BYTES: int = Field(default=5 * 1024 * 1024, gt=0)
    HZZ_MIN_RETAINED_RATIO: float = Field(default=0.5, ge=0, le=1)
    HZZ_STALE_AFTER_HOURS: float = Field(default=6.0, gt=0, allow_inf_nan=False)
