from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any


def now_ts() -> int:
    return int(time.time())


def new_id() -> str:
    return str(uuid.uuid4())


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def jaccard_score(a: str, b: str) -> float:
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
