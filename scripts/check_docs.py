#!/usr/bin/env python
"""Check documentation consistency before publishing.

Verifies that:

- Local markdown links in the README(s) and ``docs/`` resolve to existing files.
- Example file paths referenced from the README/docs exist under ``examples/``.
- The docs do not describe unsupported features by referencing the concrete
  unsupported identifiers ``get_config_as_dict`` or ``load_config_to_flask``.

Only the identifiers above are treated as forbidden. The bare words
YAML/JSON/dict are intentionally NOT banned, because the docs legitimately state
that ``get_config()`` performs no YAML/JSON/dict parsing.

Standard library only. Exits non-zero when any problem is found.
"""

import re
import sys
from pathlib import Path
from typing import List, NamedTuple

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_IDENTIFIERS = ("get_config_as_dict", "load_config_to_flask")

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_EXAMPLE_REF_RE = re.compile(r"examples/[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|ya?ml)")


class Problem(NamedTuple):
    path: str
    lineno: int
    message: str


def _doc_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for name in ("README.md", "README.zh-CN.md"):
        candidate = root / name
        if candidate.is_file():
            files.append(candidate)
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.glob("*.md")))
    return files


def _is_external(target: str) -> bool:
    lowered = target.strip().lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("#")
    )


def check_links(root: Path = ROOT) -> List[Problem]:
    """Verify that local markdown links resolve to existing files."""
    problems: List[Problem] = []
    for doc in _doc_files(root):
        text = doc.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _LINK_RE.finditer(line):
                target = match.group(1).strip()
                if _is_external(target):
                    continue
                # Strip any anchor fragment and query.
                path_part = target.split("#", 1)[0].split("?", 1)[0]
                if not path_part:
                    continue
                resolved = (doc.parent / path_part).resolve()
                if not resolved.exists():
                    rel = doc.relative_to(root).as_posix()
                    problems.append(
                        Problem(rel, lineno, f"broken link to {target!r}")
                    )
    return problems


def check_example_refs(root: Path = ROOT) -> List[Problem]:
    """Verify that referenced ``examples/...`` paths exist."""
    problems: List[Problem] = []
    for doc in _doc_files(root):
        text = doc.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _EXAMPLE_REF_RE.finditer(line):
                ref = match.group(0)
                if not (root / ref).exists():
                    rel = doc.relative_to(root).as_posix()
                    problems.append(
                        Problem(rel, lineno, f"missing example file {ref!r}")
                    )
    return problems


def check_forbidden(root: Path = ROOT) -> List[Problem]:
    """Flag references to unsupported identifiers in the docs."""
    problems: List[Problem] = []
    for doc in _doc_files(root):
        text = doc.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for identifier in FORBIDDEN_IDENTIFIERS:
                if identifier in line:
                    rel = doc.relative_to(root).as_posix()
                    problems.append(
                        Problem(
                            rel,
                            lineno,
                            f"docs must not reference unsupported {identifier!r}",
                        )
                    )
    return problems


def scan(root: Path = ROOT) -> List[Problem]:
    """Run all documentation checks and return the combined problems."""
    problems: List[Problem] = []
    problems.extend(check_links(root))
    problems.extend(check_example_refs(root))
    problems.extend(check_forbidden(root))
    return problems


def main() -> int:
    problems = scan()
    if not problems:
        print("[check_docs] OK - documentation links and references are consistent")
        return 0

    print("[check_docs] FAILED - documentation problems:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem.path}:{problem.lineno}: {problem.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
