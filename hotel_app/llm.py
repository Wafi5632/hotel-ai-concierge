"""Optional LLM adapter; the application remains fully deterministic without a key."""

from __future__ import annotations

import os
from typing import Any


def build_optional_llm() -> Any | None:
    """Create a ChatOpenAI model only when explicitly configured and installed."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.1)
