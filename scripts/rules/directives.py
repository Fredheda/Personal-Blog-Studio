import re
from pathlib import Path

DATA = Path(__file__).with_name("comment-directives.txt")
MARKER = re.compile(r"^(#+|/{2,}|/\*+)\s*")


def load() -> dict[str, list[re.Pattern[str]]]:
    patterns: dict[str, list[re.Pattern[str]]] = {"python": [], "ts": [], "hash": []}
    for row in DATA.read_text().splitlines():
        if row.strip():
            language, regex = row.split("\t", 1)
            patterns[language].append(re.compile(regex))
    return patterns


PATTERNS = load()


def is_directive(text: str, language: str) -> bool:
    body = MARKER.sub("", text.strip(), count=1)
    return any(pattern.search(body) for pattern in PATTERNS[language])
