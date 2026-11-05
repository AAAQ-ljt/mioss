from __future__ import annotations

import re
from dataclasses import dataclass, field

BRACKETS_RE = re.compile(r"[{}\[\]]")
YEAR_RE = re.compile(r"^year \d{4}$")

QUALITY_META = {
    "4k",
    "8k",
    "amazing quality",
    "artist collaboration",
    "absurdres",
    "best illustration",
    "best quality",
    "digital illustration",
    "high complexity",
    "high detail",
    "highres",
    "incredibly absurdres",
    "low effort",
    "masterpiece",
    "medium complexity",
    "newest",
    "no text",
    "ultra-detailed",
    "ultra high resolution",
    "variety+",
    "very aesthetic",
}


@dataclass
class SanitizedTags:
    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    parsed_count: int = 0

    @property
    def positive_text(self) -> str:
        return ", ".join(self.positive)

    @property
    def negative_text(self) -> str:
        return ", ".join(self.negative)

    @property
    def artist_dropped_count(self) -> int:
        return sum(1 for item in self.dropped if item["reason"] == "artist")

    @property
    def artist_ratio(self) -> float:
        if self.parsed_count == 0:
            return 0.0
        return self.artist_dropped_count / self.parsed_count

    @property
    def content_tags(self) -> list[str]:
        return [
            tag
            for tag in self.positive
            if tag not in QUALITY_META and not YEAR_RE.match(tag)
        ]

    @property
    def moss_usable(self) -> bool:
        return bool(self.content_tags)


def normalize_tag(raw: str) -> str:
    text = BRACKETS_RE.sub(" ", raw)
    text = text.replace("::", " ")
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\byear\s*(\d{4})\b", r"year \1", text)
    return text


def is_meaningful_tag(tag: str) -> bool:
    return bool(re.search(r"[a-z0-9]", tag))


def artist_keys(raw: str) -> set[str]:
    basic = normalize_tag(raw)
    without_paren = re.sub(r"\s*\(([^)]*)\)\s*", r" \1 ", basic)
    without_paren = re.sub(r"\s+", " ", without_paren).strip()
    return {key for key in (basic, without_paren) if key}


def parse_tag_string(tags: str) -> list[tuple[float | None, str]]:
    text = (tags or "").replace("\n", ",")
    segments: list[tuple[float | None, str]] = []
    index = 0
    length = len(text)

    while index < length:
        while index < length and text[index] in ", ":
            index += 1
        if index >= length:
            break

        weight_match = re.match(r"(-?\d+(?:\.\d+)?)::", text[index:])
        if weight_match:
            content_start = index + weight_match.end()
            content_end = text.find("::", content_start)
            if content_end != -1:
                weight = float(weight_match.group(1))
                for token in text[content_start:content_end].split(","):
                    if token.strip():
                        segments.append((weight, token))
                index = content_end + 2
                continue
            comma = text.find(",", index)
            if comma == -1:
                comma = length
            token = text[index:comma]
            if token.strip():
                segments.append((None, token))
            index = comma + 1
            continue

        if text.startswith("::", index):
            content_start = index + 2
            content_end = text.find("::", content_start)
            if content_end != -1:
                for token in text[content_start:content_end].split(","):
                    if token.strip():
                        segments.append((None, token))
                index = content_end + 2
                continue
            index += 2
            continue

        comma = text.find(",", index)
        if comma == -1:
            comma = length
        token = text[index:comma]
        if token.strip():
            segments.append((None, token))
        index = comma + 1

    return segments


def sanitize_tags(
    tags: str,
    artist_set: set[str],
    negative_policy: str = "to_negative",
) -> SanitizedTags:
    result = SanitizedTags()
    seen_positive: set[str] = set()
    seen_negative: set[str] = set()

    for weight, raw_tag in parse_tag_string(tags):
        tag = normalize_tag(raw_tag)
        if not tag:
            continue
        if not is_meaningful_tag(tag):
            continue
        result.parsed_count += 1

        if tag.startswith("artist:"):
            result.dropped.append({"tag": tag, "reason": "artist"})
            continue
        if artist_keys(tag) & artist_set:
            result.dropped.append({"tag": tag, "reason": "artist"})
            continue

        if weight is not None and weight < 0:
            if negative_policy == "drop" or (negative_policy == "only_minus2" and weight > -2):
                result.dropped.append({"tag": tag, "reason": "negative_weight"})
            elif tag not in seen_negative:
                seen_negative.add(tag)
                result.negative.append(tag)
            continue

        if tag not in seen_positive:
            seen_positive.add(tag)
            result.positive.append(tag)

    return result


def normalize_tag_list(tags: str) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for token in re.split(r"[,\n]", tags or ""):
        tag = normalize_tag(token)
        if tag and tag not in seen:
            seen.add(tag)
            output.append(tag)
    return ", ".join(output)
