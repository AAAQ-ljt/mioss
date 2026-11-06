from __future__ import annotations

import json
import re
from typing import Any

NSFW_RATINGS = {"r18", "r18g", "nsfw", "restricted"}

REGULAR_KEYWORDS = {
    "character": [
        "角色", "oc", "人外", "种族", "身份", "图鉴", "属性", "二次元", "二创", "发型", "眼睛",
        "elf", "demon", "angel", "vampire", "succubus", "witch", "mage", "knight", "princess",
        "catgirl", "fox girl", "dragon girl", "monster girl", "orc", "goblin", "android",
    ],
    "outfit": [
        "服装", "泳装", "衬衫", "裙子", "鞋子", "袜子", "套装", "裤子", "礼服", "上衣", "传统服饰",
        "秋季穿搭", "配饰", "耳饰", "发饰", "头饰", "颈部配饰", "身体配饰", "手部配饰", "面部配饰",
        "制服", "校服", "军装", "职业", "民族", "衣柜", "dress", "shirt", "skirt", "uniform",
        "swimsuit", "bikini", "boots", "shoes", "socks", "stockings", "hat", "cap", "jacket",
        "coat", "cloak", "armor", "gloves", "ribbon", "bow", "belt", "necklace", "earrings",
        "lingerie", "panties", "bra", "pantyhose", "thighhighs",
    ],
    "scene": [
        "场景", "背景", "自然", "室内", "室外", "城市", "风景", "建筑", "地貌", "植被", "天气",
        "森林", "树林", "海边", "海滩", "山", "天空", "夜晚", "白天", "黄昏", "日落", "室内",
        "室外", "街道", "教室", "咖啡馆", "bedroom", "room", "forest", "city", "street",
        "beach", "mountain", "sky", "night", "sunset", "landscape", "background", "indoors",
        "outdoors", "classroom", "cafe",
    ],
    "composition": [
        "构图", "视角", "镜头", "光影", "色彩", "景别", "特写", "全景", "中景", "近景", "远景",
        "仰视", "俯视", "斜角", "广角", "景深", "透视", "close-up", "full body", "upper body",
        "cowboy shot", "from above", "from below", "from side", "from behind", "dutch angle",
        "wide shot", "depth of field", "perspective", "foreshortening", "dynamic angle",
    ],
    "style": [
        "风格", "画风", "黑白", "彩色", "写实", "水彩", "素描", "线稿", "赛璐璐", "网点",
        "monochrome", "grayscale", "watercolor", "sketch", "lineart", "realistic",
        "photorealistic", "cinematic", "anime style", "manga", "retro", "vintage",
    ],
    "action": [
        "表情", "姿势", "手势", "动作", "互动", "行为", "移动", "情绪", "姿势-", "手势",
        "standing", "sitting", "lying", "walking", "running", "smile", "open mouth",
        "looking at viewer", "pose", "fighting", "hug", "kiss", "dance", "jump", "crying",
        "expressionless", "blush", "closed eyes", "hand up", "leaning forward",
    ],
    "prop": [
        "武器", "道具", "生物", "怪物", "植物", "动物", "剑", "法杖", "书", "花", "蘑菇",
        "sword", "weapon", "staff", "book", "flower", "mushroom", "animal", "dog", "cat",
        "dragon", "monster", "creature", "plant", "tree", "food", "cup",
    ],
    "misc": [
        "漫画", "分格", "对话框", "拟声词", "自然语言", "杂项", "排版", "文字", "comic",
        "panel", "speech bubble", "text", "manga page", "4koma",
    ],
}

NSFW_TAG_KEYWORDS = {
    "nsfw_extreme": [
        "gore", "guro", "blood", "death", "ryona", "amputation", "corpse", "vore",
        "dismember", "torture", "snuff", "r18g",
    ],
    "nsfw_nonhuman": [
        "tentacle", "monster", "orc", "goblin", "beast", "alien", "insect", "worm",
        "non-human", "nonhuman", "demon", "slime",
    ],
    "nsfw_multi": [
        "3some", "threesome", "group", "gangbang", "orgy", "multiple boys", "multiple girls",
        "2boys", "2girls", "3boys", "3girls", "4boys", "4girls", "ffm", "mmf",
    ],
    "nsfw_relation": ["yuri", "lesbian", "yaoi", "futanari", "straight", "bisexual", "couple"],
    "nsfw_outfit": [
        "lingerie", "bikini", "panties", "bra", "stockings", "pantyhose", "thighhighs",
        "swimsuit", "nude", "naked", "see-through", "bondage", "bdsm", "latex", "leotard",
    ],
    "nsfw_scene": ["bed", "bath", "pool", "dungeon", "onsen", "shower", "toilet", "cave"],
    "nsfw_misc": ["comic", "panel", "differential", "sequence", "4koma", "manga page", "multiple panels"],
}

PROVENANCE = [
    "群友", "社区", "画廊", "第", "卷", "编纂者杂项", "作品", "韩网", "其他模型",
    "收录", "杂图", "杂项涩涩", "网络色色串",
]

REGULAR_PATH_RULES = [
    ("outfit", ["服装", "泳装", "衬衫", "裙子", "鞋子", "袜子", "套装", "裤子", "礼服", "上衣",
                "传统服饰", "秋季穿搭", "配饰", "耳饰", "发饰", "头饰", "衣柜", "发型"]),
    ("scene", ["场景", "背景", "自然", "室内", "室外", "城市", "风景", "建筑", "地貌", "植被"]),
    ("composition", ["构图", "视角", "镜头", "光影", "色彩", "景别"]),
    ("style", ["风格", "画风"]),
    ("action", ["表情", "姿势", "手势", "动作", "互动", "行为", "移动"]),
    ("character", ["角色", "oc", "人外", "种族", "身份", "图鉴", "属性", "二创"]),
    ("prop", ["武器", "道具", "生物", "怪物", "植物", "动物"]),
]

NSFW_PATH_RULES = [
    ("nsfw_extreme", ["r18g", "重口", "猎奇", "血腥", "断肢"]),
    ("nsfw_nonhuman", ["非人", "兽", "触手", "怪物", "异种"]),
    ("nsfw_outfit", ["涩涩服饰", "服饰、人设", "情趣", "内衣", "服装", "服饰"]),
    ("nsfw_relation", ["百合", "耽美", "男同", "女同", "关系"]),
    ("nsfw_multi", ["多男", "多女", "多人"]),
    ("nsfw_single", ["单女", "单男"]),
    ("nsfw_scene", ["场景", "背景", "地点", "道具"]),
    ("nsfw_misc", ["连续", "差分", "群友色色", "网络色色", "杂项涩涩", "构图", "镜头"]),
]


def _path(entry: dict[str, Any]) -> str:
    try:
        return " / ".join(json.loads(entry.get("category_path_json") or "[]")).lower()
    except json.JSONDecodeError:
        return ""


def _tag_text(entry: dict[str, Any]) -> str:
    return (entry.get("tags_positive") or entry.get("tags_raw") or "").lower()


def _score_tags(text: str, rules: dict[str, list[str]]) -> dict[str, int]:
    scores = {}
    for category, keywords in rules.items():
        scores[category] = sum(1 for keyword in keywords if keyword in text)
    return scores


def _source_category(path: str, rules: list[tuple[str, list[str]]]) -> str | None:
    for category, keywords in rules:
        if any(keyword in path for keyword in keywords):
            if category in {"nsfw_misc", "misc"}:
                return category
            return category
    return None


def _is_provenance(path: str) -> bool:
    return any(keyword in path for keyword in PROVENANCE)


def domain_for(codex_id: str, codex_nsfw: int, rating: str | None, tags: str) -> str:
    if codex_id.startswith("artist_"):
        return "reference"
    if rating in NSFW_RATINGS:
        return "nsfw"
    if codex_nsfw:
        return "nsfw"
    if re.search(r"\bnsfw\b", tags or ""):
        return "nsfw"
    return "regular"


def classify_entry(entry: dict[str, Any], codex_nsfw: int = 0) -> tuple[str, str, list[str]]:
    codex_id = entry.get("codex_id") or ""
    tags = _tag_text(entry)
    domain = domain_for(codex_id, codex_nsfw, entry.get("rating"), tags)
    if domain == "reference":
        return "reference", "artist_ref", ["artist_ref"]

    path = _path(entry)
    if domain == "nsfw":
        primary = _source_category(path, NSFW_PATH_RULES)
        scores = _score_tags(tags, NSFW_TAG_KEYWORDS)
        if primary is None:
            primary = max(scores, key=scores.get) if max(scores.values(), default=0) > 0 else "nsfw_single"
        labels = [primary]
        for category, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
            if score > 0 and category not in labels:
                labels.append(category)
            if len(labels) >= 3:
                break
        return domain, primary, labels

    primary = _source_category(path, REGULAR_PATH_RULES)
    scores = _score_tags(tags, REGULAR_KEYWORDS)
    if primary is None or (primary in {"misc"} and max(scores.values(), default=0) > 0):
        primary = max(scores, key=scores.get) if max(scores.values(), default=0) > 0 else "misc"
    labels = [primary]
    for category, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        if score > 0 and category not in labels:
            labels.append(category)
        if len(labels) >= 3:
            break
    return domain, primary, labels
