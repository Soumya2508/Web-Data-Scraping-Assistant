from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WDSP_", extra="ignore")

    http_connect_timeout_s: float = 5.0
    http_read_timeout_s: float = 20.0
    http_max_bytes: int = 2_000_000

    exports_dir: str = "exports"

    # Important for safe deployment: block URLs that resolve to private/internal IP ranges.
    # Set WDSP_BLOCK_PRIVATE_NETWORKS=false only if you fully trust users of this service.
    block_private_networks: bool = True

    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _parse_cors_allow_origins(cls, v: Any) -> Any:
        # Support either:
        # - JSON array (recommended): WDSP_CORS_ALLOW_ORIGINS='["https://your-frontend"]'
        # - Comma-separated string:   WDSP_CORS_ALLOW_ORIGINS='https://a,https://b'
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                return v
            return [p.strip() for p in s.split(",") if p.strip()]
        return v


settings = Settings()
