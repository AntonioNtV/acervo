"""Import rules of skill `repo-structure`, checked on the AST of every module in `src/acervo`."""

import ast
from collections.abc import Iterator
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
PACKAGE = SRC / "acervo"

LAYERS = {"core", "domain", "schemas", "db", "repositories", "services", "pipeline", "api", "worker"}

# Layers each layer must not import: nothing upward, plus the skill's explicit rules.
FORBIDDEN_LAYERS = {
    "core": LAYERS - {"core"},
    "domain": LAYERS - {"core", "domain"},
    "schemas": LAYERS - {"core", "domain", "schemas"},
    "db": {"repositories", "services", "pipeline", "api", "worker"},
    "repositories": {"services", "pipeline", "api", "worker"},
    "pipeline": {"db", "repositories", "services", "api", "worker"},
    "services": {"db", "api", "worker"},
    "api": {"db", "repositories", "pipeline", "worker"},
    "worker": {"db", "repositories", "pipeline", "api"},
}

# No SQLAlchemy, FastAPI or httpx below services, except in db, repositories and api.
FRAMEWORKS = {"sqlalchemy", "fastapi", "httpx"}
FRAMEWORK_FREE_LAYERS = {"core", "domain", "schemas", "pipeline"}

# Composition roots wire the database at startup or per request; that is all they may take from the lower layers.
COMPOSITION_ROOTS = {
    Path("api/main.py"): "acervo.db.session",
    Path("api/deps.py"): "acervo.repositories.uow",
    Path("worker/__main__.py"): "acervo.db.session",
    Path("worker/activities.py"): "acervo.repositories.uow",
}


def _modules() -> list[Path]:
    modules = sorted(PACKAGE.rglob("*.py"))
    assert modules, f"no modules found under {PACKAGE}"
    return modules


def _package_of(path: Path) -> str:
    return path.relative_to(PACKAGE).parts[0]


def _layer_of_module(path: Path) -> str | None:
    first = _package_of(path)
    return first if first in LAYERS else None


def _package_of_import(name: str) -> str | None:
    parts = name.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "acervo" else None


def _imports(path: Path) -> Iterator[str]:
    """Dotted names imported by the module, relative imports resolved to absolute ones."""
    package = path.relative_to(SRC).with_suffix("").parts[:-1]
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ".".join(package[: len(package) - node.level + 1]) if node.level else ""
            module = ".".join(part for part in (base, node.module) if part)
            yield module
            # `from acervo import db` names the layer in the alias, not in the module.
            yield from (f"{module}.{alias.name}" for alias in node.names)


def test_no_import_against_the_layers() -> None:
    violations = []
    for path in _modules():
        layer = _layer_of_module(path)
        if layer is None:
            continue
        allowed = COMPOSITION_ROOTS.get(path.relative_to(PACKAGE))
        for name in _imports(path):
            if allowed and (name == allowed or name.startswith(allowed + ".")):
                continue
            if _package_of_import(name) in FORBIDDEN_LAYERS[layer] or (
                layer in FRAMEWORK_FREE_LAYERS and name.split(".")[0] in FRAMEWORKS
            ):
                violations.append(f"{path.relative_to(SRC)} ({layer}) imports {name}")

    assert not violations, "\n".join(sorted(set(violations)))
