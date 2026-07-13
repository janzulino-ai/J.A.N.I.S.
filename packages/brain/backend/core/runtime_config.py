"""Config runtime JANIS — toggle PRO e provider ragionamento (persistito)."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.Runtime")

RUNTIME_PATH = None  # unused — kept for compat


def _runtime_path() -> Path:
    return Path(settings.JANIS_PROJECT_DIR) / "data" / "runtime.json"

REASONING_PROVIDERS = ("ollama", "cursor", "openrouter", "auto")

CURSOR_REASONING_MODELS = (
    "composer-2.5",
    "composer-2.5-fast",
    "gpt-5.3-codex-high-fast",
    "gpt-5.5-medium",
    "claude-4.6-sonnet-medium-thinking",
)


@dataclass
class RuntimeConfig:
    paid_mode: bool = False
    reasoning_provider: str = "ollama"
    cursor_reasoning_model: str = ""
    cursor_code_enabled: bool = True
    openrouter_when_paid: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    def normalized(self) -> RuntimeConfig:
        rp = (self.reasoning_provider or "ollama").lower().strip()
        if rp not in REASONING_PROVIDERS:
            rp = "ollama"
        model = self.cursor_reasoning_model or settings.CURSOR_MODEL
        if model not in CURSOR_REASONING_MODELS:
            model = settings.CURSOR_MODEL or CURSOR_REASONING_MODELS[0]
        return RuntimeConfig(
            paid_mode=bool(self.paid_mode),
            reasoning_provider=rp,
            cursor_reasoning_model=model,
            cursor_code_enabled=bool(self.cursor_code_enabled),
            openrouter_when_paid=bool(self.openrouter_when_paid),
        )


_runtime: RuntimeConfig | None = None


def load_runtime() -> RuntimeConfig:
    global _runtime
    if _runtime is not None:
        return _runtime
    path = _runtime_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            _runtime = RuntimeConfig(**{k: v for k, v in raw.items() if k in RuntimeConfig.__dataclass_fields__}).normalized()
            return _runtime
        except Exception as e:
            logger.warning("runtime.json invalid: %s", e)
    _runtime = RuntimeConfig().normalized()
    return _runtime


def save_runtime(cfg: RuntimeConfig) -> RuntimeConfig:
    global _runtime
    cfg = cfg.normalized()
    path = _runtime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg.to_dict(), indent=2), encoding="utf-8")
    _runtime = cfg
    logger.info("Runtime saved: paid=%s reasoning=%s", cfg.paid_mode, cfg.reasoning_provider)
    return cfg


def get_runtime() -> RuntimeConfig:
    return load_runtime()


def effective_reasoning_provider() -> str:
    rt = get_runtime()
    if not rt.paid_mode:
        return (settings.LLM_PROVIDER or "ollama").lower().strip()
    return rt.reasoning_provider
