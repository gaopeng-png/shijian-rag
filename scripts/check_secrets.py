from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "venv", "storage", "chroma_history_db", "__pycache__"}
TEXT_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".md", ".json", ".jsonl", ".txt", ".css"}
PATTERNS = {
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "literal API key assignment": re.compile(
        r"(?i)(?:api[_-]?key|secret)\s*[:=]\s*['\"][A-Za-z0-9_-]{20,}['\"]"
    ),
}


def main() -> None:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.name == Path(__file__).name or any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    if findings:
        raise SystemExit("possible secrets detected:\n" + "\n".join(findings))
    print("secret scan passed")


if __name__ == "__main__":
    main()
