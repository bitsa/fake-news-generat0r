import importlib.util
import re
from pathlib import Path


def _load_migration():
    versions_dir = Path(__file__).parents[2] / "migrations" / "versions"
    revision_files = [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"]
    assert revision_files, "Expected at least 1 revision file"

    loaded: list[tuple[object, Path]] = []
    for path in revision_files:
        spec = importlib.util.spec_from_file_location(f"_migration_{path.stem}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded.append((module, path))

    roots = [
        (m, p) for (m, p) in loaded if getattr(m, "down_revision", object()) is None
    ]
    assert len(roots) == 1, f"Expected 1 root migration, found {len(roots)}"
    module, path = roots[0]
    return module, path.read_text()


def test_root_revision_exists():
    # Asserts a root migration (down_revision = None) can be found
    _load_migration()


def test_down_revision_is_none():
    module, _ = _load_migration()
    assert module.down_revision is None


def test_revision_is_string():
    module, _ = _load_migration()
    assert isinstance(module.revision, str)
    assert len(module.revision) > 0


def test_migration_imports_source():
    _, source = _load_migration()
    assert "from app.sources import Source" in source


def test_migration_derives_labels_from_source():
    _, source = _load_migration()
    # Labels must not appear as adjacent string literals in declaration order.
    # The pattern we forbid is all three values quoted and close together in sequence.
    forbidden = re.compile(
        r"""["']NYT["'].*?["']NPR["'].*?["']Guardian["']""", re.DOTALL
    )
    assert not forbidden.search(
        source
    ), "Migration hardcodes source labels instead of deriving from Source enum"


def test_upgrade_downgrade_callable():
    module, _ = _load_migration()
    assert callable(module.upgrade)
    assert callable(module.downgrade)
