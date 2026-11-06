from __future__ import annotations

import re
from typing import Any

from .sanitize import normalize_tag, parse_tag_string


def _decoration(token: str) -> tuple[str, float]:
    braces = token.count("{")
    brackets = token.count("[")
    tag = normalize_tag(token)
    factor = (1.05**braces) * (0.95**brackets)
    return tag, factor


def _format_tag(tag: str, weight: float) -> str:
    weight = max(0.05, min(2.0, weight))
    if abs(weight - 1.0) < 0.005:
        return tag
    text = f"{weight:.2f}".rstrip("0").rstrip(".")
    return f"({tag}:{text})"


def to_sd_weights(tags: str) -> dict[str, Any]:
    positive: list[str] = []
    negative: list[str] = []
    seen_positive: set[str] = set()
    seen_negative: set[str] = set()

    for weight, raw_token in parse_tag_string(tags or ""):
        tag, decoration = _decoration(raw_token)
        if not tag:
            continue
        if weight is not None and weight < 0:
            if tag not in seen_negative:
                seen_negative.add(tag)
                negative.append(tag)
            continue
        final_weight = decoration * (weight if weight is not None else 1.0)
        formatted = _format_tag(tag, final_weight)
        if formatted not in seen_positive:
            seen_positive.add(formatted)
            positive.append(formatted)

    return {
        "positive": ", ".join(positive),
        "negative": ", ".join(negative),
        "positive_count": len(positive),
        "negative_count": len(negative),
    }


def decorate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sd = to_sd_weights(entry.get("tags_raw") or "")
    entry["prompt_sd_positive"] = sd["positive"]
    entry["prompt_sd_negative"] = sd["negative"]
    return entry
