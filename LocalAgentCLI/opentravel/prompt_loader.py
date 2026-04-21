from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template


_PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs: str) -> str:
    return Template(load_prompt(name)).substitute(**kwargs)
