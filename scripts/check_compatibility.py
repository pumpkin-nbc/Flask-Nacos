#!/usr/bin/env python
"""Check that the project stays Python 3.8 compatible and free of unsupported features.

Static checks (no imports, no network):

- No PEP 604 unions in annotations (``str | None``) -- use ``Optional[str]``.
- No PEP 585 builtin generics in annotations (``list[str]``, ``dict[str, str]``)
  -- use ``typing.List`` / ``typing.Dict``.
- No ``match`` / ``case`` statements (Python 3.10+).
- The library source does not reference ``get_config_as_dict`` /
  ``load_config_to_flask`` and does not implement YAML parsing.
- No PyYAML dependency in pyproject.toml.

Syntax checks use ``ast`` so the checker's own pattern strings never self-trigger.
Documentation that merely states "YAML is not supported" is fine (docs are not
scanned here).

Standard library only. Exits non-zero when any problem is found.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Iterable, List, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

# Directories whose *.py files must stay Python 3.8 syntax-compatible.
SYNTAX_SCAN_DIRS = ("flask_nacos", "scripts", "examples")
# Directories checked for unsupported-feature implementations (the library).
SOURCE_SCAN_DIRS = ("flask_nacos",)

BUILTIN_GENERICS = {"list", "dict", "tuple", "set", "frozenset"}

# ``get_config_as_dict`` must never appear as an implementation. (Note:
# ``load_config_to_flask`` exists only as a reserved ``NotImplementedError`` stub
# and is intentionally not scanned here.)
FORBIDDEN_IDENTIFIERS = ("get_config_as_dict",)
YAML_MARKERS = ("import yaml", "from yaml", "yaml.load", "yaml.safe_load")

_MATCH_RE = re.compile(r"^\s*(match|case)\b.*:\s*$")


class Problem(NamedTuple):
    path: str
    lineno: int
    message: str


def _iter_py_files(root: Path, dirs: Iterable[str]) -> Iterable[Path]:
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if path.resolve() == SELF:
                continue
            yield path


def _annotation_nodes(tree: ast.AST) -> Iterable[ast.AST]:
    """Yield every annotation node in the module."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            all_args = list(
                getattr(args, "posonlyargs", []) or []
            ) + list(args.args) + list(args.kwonlyargs)
            if args.vararg:
                all_args.append(args.vararg)
            if args.kwarg:
                all_args.append(args.kwarg)
            for arg in all_args:
                if arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            yield node.annotation


def _check_annotation(annotation: ast.AST, rel: str, problems: List[Problem]) -> None:
    for node in ast.walk(annotation):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            problems.append(
                Problem(
                    rel,
                    getattr(node, "lineno", 0),
                    "PEP 604 union (X | Y); use typing.Optional/Union",
                )
            )
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in BUILTIN_GENERICS:
                name = node.value.id
                problems.append(
                    Problem(
                        rel,
                        getattr(node, "lineno", 0),
                        f"PEP 585 builtin generic ({name}[...]); use typing.{name.capitalize()}",
                    )
                )


def _check_syntax_file(path: Path, rel: str, problems: List[Problem]) -> None:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        # On Python 3.8 match/case is a syntax error; confirm with a regex.
        for lineno, line in enumerate(source.splitlines(), start=1):
            if _MATCH_RE.match(line):
                problems.append(Problem(rel, lineno, "match/case is not Python 3.8 compatible"))
                return
        problems.append(Problem(rel, exc.lineno or 0, f"syntax not 3.8-compatible: {exc.msg}"))
        return

    for annotation in _annotation_nodes(tree):
        _check_annotation(annotation, rel, problems)

    match_type = getattr(ast, "Match", None)
    if match_type is not None:
        for node in ast.walk(tree):
            if isinstance(node, match_type):
                problems.append(
                    Problem(
                        rel,
                        getattr(node, "lineno", 0),
                        "match/case is not Python 3.8 compatible",
                    )
                )


def _check_source_file(path: Path, rel: str, problems: List[Problem]) -> None:
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for identifier in FORBIDDEN_IDENTIFIERS:
            if identifier in line:
                problems.append(
                    Problem(rel, lineno, f"unsupported identifier {identifier!r} in source")
                )
        for marker in YAML_MARKERS:
            if marker in line:
                problems.append(
                    Problem(rel, lineno, f"YAML parsing is not supported ({marker!r})")
                )


def scan(root: Path = ROOT) -> List[Problem]:
    """Run all compatibility checks and return the combined problems."""
    problems: List[Problem] = []

    for path in _iter_py_files(root, SYNTAX_SCAN_DIRS):
        _check_syntax_file(path, path.relative_to(root).as_posix(), problems)

    for path in _iter_py_files(root, SOURCE_SCAN_DIRS):
        _check_source_file(path, path.relative_to(root).as_posix(), problems)

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        content = pyproject.read_text(encoding="utf-8")
        for lineno, line in enumerate(content.splitlines(), start=1):
            if "pyyaml" in line.lower():
                problems.append(
                    Problem("pyproject.toml", lineno, "PyYAML dependency is not allowed")
                )

    return problems


def main() -> int:
    problems = scan()
    if not problems:
        print("[check_compatibility] OK - Python 3.8 compatible; no unsupported features")
        return 0

    print("[check_compatibility] FAILED - compatibility problems:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem.path}:{problem.lineno}: {problem.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
