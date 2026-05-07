import importlib.util
from pathlib import Path


def _load_chat_migration():
    versions_dir = Path(__file__).parents[2] / "migrations" / "versions"
    revision_files = [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"]

    for path in revision_files:
        spec = importlib.util.spec_from_file_location(f"_migration_{path.stem}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if getattr(module, "down_revision", None) == "cfe2a836394a":
            return module, path.read_text()

    raise AssertionError(
        "No revision with down_revision='cfe2a836394a' (chat_messages migration)"
    )


def test_chat_migration_down_revision_is_genesis():
    module, _ = _load_chat_migration()
    assert module.down_revision == "cfe2a836394a"
    assert isinstance(module.revision, str)
    assert len(module.revision) > 0


def test_chat_migration_upgrade_creates_chat_messages_table_and_index():
    _, source = _load_chat_migration()
    assert 'op.create_table(\n        "chat_messages"' in source or (
        'op.create_table("chat_messages"' in source
    )
    assert (
        'op.create_index(\n        "ix_chat_messages_article_id_created_at"' in source
        or ('op.create_index("ix_chat_messages_article_id_created_at"' in source)
    )


def test_chat_migration_downgrade_drops_chat_messages_table_and_index():
    _, source = _load_chat_migration()
    assert 'op.drop_table("chat_messages")' in source
    assert "op.drop_index(" in source
    assert '"ix_chat_messages_article_id_created_at"' in source


def test_chat_migration_upgrade_and_downgrade_callable():
    module, _ = _load_chat_migration()
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_chat_migration_role_check_constraint_named_and_lists_both_roles():
    _, source = _load_chat_migration()
    assert "ck_chat_messages_role" in source
    assert "'user'" in source
    assert "'assistant'" in source
