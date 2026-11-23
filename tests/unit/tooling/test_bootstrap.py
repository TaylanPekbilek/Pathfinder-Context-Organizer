# tests/unit/tooling/test_bootstrap.py
from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path


def test_pyproject_structure() -> None:
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists(), "pyproject.toml must exist"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    # build-system
    build = data.get("build-system", {})
    assert build.get("build-backend") == "uv_build"
    requires = build.get("requires", [])
    assert any(r.startswith("uv_build") for r in requires)

    # project
    project = data.get("project", {})
    assert project.get("name") == "pathfinder-context-organizer"
    assert project.get("version") == "0.1.0rc1"
    assert project.get("requires-python") == ">=3.13"
    assert project.get("readme") == "README.md"
    assert "description" in project

    # dependency-groups
    dep_groups = data.get("dependency-groups", {})
    dev = dep_groups.get("dev", [])
    assert any("pytest" in d for d in dev)
    assert any("mypy" in d for d in dev)
    assert any("ruff" in d for d in dev)
    # must NOT use [project.optional-dependencies]
    assert "optional-dependencies" not in data.get("project", {})

    # tool config
    assert "pytest" in data.get("tool", {})
    assert "mypy" in data.get("tool", {})
    assert "ruff" in data.get("tool", {})


def test_src_layout_exists() -> None:
    assert Path("src/pathfinder_context_organizer/__init__.py").exists()
    assert Path("src/pathfinder_context_organizer/py.typed").exists()
    assert Path("README.md").exists()


def test_domain_import_isolation() -> None:
    domain_root = Path("src/pathfinder_context_organizer/domain")
    if not domain_root.exists():
        return

    stdlib_modules = set(sys.stdlib_module_names)
    allowed_internal_prefix = "pathfinder_context_organizer.domain"

    for py in domain_root.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    parts = name.split(".")
                    top = parts[0]
                    # stdlib allowed
                    if top in stdlib_modules:
                        continue
                    # project-internal: only domain subpackage allowed
                    if name.startswith(allowed_internal_prefix + "."):
                        continue
                    if name == allowed_internal_prefix:
                        continue
                    # everything else forbidden
                    assert False, f"{py}: forbidden import '{name}' in domain layer"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module
                    # relative import escaping domain?
                    if node.level > 0:
                        assert False, (
                            f"{py}: relative import forbidden in domain layer ('{module}' level {node.level})"
                        )
                        continue
                    # absolute import
                    parts = module.split(".")
                    top = parts[0]
                    if top in stdlib_modules:
                        continue
                    if module.startswith(allowed_internal_prefix + "."):
                        continue
                    if module == allowed_internal_prefix:
                        continue
                    assert False, f"{py}: forbidden import from '{module}' in domain layer"

