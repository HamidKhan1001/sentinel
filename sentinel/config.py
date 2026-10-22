import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("SENTINEL_MODEL", "claude-sonnet-5-5")
    api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    max_steps: int = 14
    price_in: float = 3.0   # USD / Mtok, for cost reporting
    price_out: float = 15.0


settings = Settings()
