import sqlalchemy as sa

from app.models import ChatMessage


def test_chat_message_table_columns_match_spec():
    cols = ChatMessage.__table__.c

    assert ChatMessage.__tablename__ == "chat_messages"

    assert isinstance(cols.id.type, sa.Integer)
    assert cols.id.primary_key is True
    assert cols.id.autoincrement is True

    assert isinstance(cols.article_id.type, sa.Integer)
    assert cols.article_id.nullable is False

    assert isinstance(cols.role.type, sa.String)
    assert cols.role.type.length == 20
    assert cols.role.nullable is False

    assert isinstance(cols.content.type, sa.Text)
    assert cols.content.nullable is False

    assert isinstance(cols.is_error.type, sa.Boolean)
    assert cols.is_error.nullable is False

    assert isinstance(cols.request_id.type, sa.String)
    assert cols.request_id.type.length == 64
    assert cols.request_id.nullable is True

    assert isinstance(cols.created_at.type, sa.DateTime)
    assert cols.created_at.type.timezone is True
    assert cols.created_at.nullable is False


def test_chat_message_role_check_constraint_rejects_other_values():
    check_constraints = [
        c
        for c in ChatMessage.__table__.constraints
        if isinstance(c, sa.CheckConstraint)
    ]
    role_check = [c for c in check_constraints if c.name == "ck_chat_messages_role"]
    assert len(role_check) == 1
    sql_text = str(role_check[0].sqltext)
    assert "'user'" in sql_text
    assert "'assistant'" in sql_text


def test_chat_message_composite_index_on_article_id_and_created_at():
    indexes = list(ChatMessage.__table__.indexes)
    target = [i for i in indexes if i.name == "ix_chat_messages_article_id_created_at"]
    assert len(target) == 1
    cols = [c.name for c in target[0].columns]
    assert cols == ["article_id", "created_at"]


def test_chat_message_is_error_server_default_false_and_created_at_default_now():
    cols = ChatMessage.__table__.c

    is_error_default = cols.is_error.server_default
    assert is_error_default is not None
    assert "false" in str(is_error_default.arg).lower()

    created_at_default = cols.created_at.server_default
    assert created_at_default is not None
    assert "now" in str(created_at_default.arg).lower()


def test_chat_message_request_id_nullable_and_no_unique_constraint():
    cols = ChatMessage.__table__.c
    assert cols.request_id.nullable is True
    assert cols.request_id.unique is not True

    unique_on_request_id = any(
        isinstance(c, sa.UniqueConstraint) and list(c.columns.keys()) == ["request_id"]
        for c in ChatMessage.__table__.constraints
    )
    assert unique_on_request_id is False


def test_chat_message_article_id_fk_cascade_delete():
    col = ChatMessage.__table__.c.article_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.column.table.name == "articles"
    assert fk.column.name == "id"
    assert fk.ondelete == "CASCADE"
