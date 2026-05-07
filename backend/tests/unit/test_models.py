import sqlalchemy as sa

from app.models import Article, ArticleFake, Base, ChatMessage
from app.sources import Source


def test_tablenames():
    assert Article.__tablename__ == "articles"
    assert ArticleFake.__tablename__ == "article_fakes"
    assert ChatMessage.__tablename__ == "chat_messages"


def test_metadata_tables():
    assert set(Base.metadata.tables) == {"articles", "article_fakes", "chat_messages"}


def test_article_source_enum_binding():
    col_type = Article.__table__.c.source.type
    assert isinstance(col_type, sa.Enum)
    assert col_type.name == "source_type"
    assert col_type.enums == [m.value for m in Source]


def test_article_description_nullable():
    assert Article.__table__.c.description.nullable is False


def test_article_url_unique():
    col = Article.__table__.c.url
    unique_via_col = col.unique is True
    unique_via_constraint = any(
        isinstance(c, sa.UniqueConstraint) and list(c.columns.keys()) == ["url"]
        for c in Article.__table__.constraints
    )
    assert unique_via_col or unique_via_constraint


def test_article_fake_pk_is_fk():
    col = ArticleFake.__table__.c.article_id
    assert col.primary_key is True
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.column.table.name == "articles"
    assert fk.column.name == "id"
    assert fk.ondelete == "CASCADE"


def test_article_fake_transform_status_check():
    check_constraints = [
        c
        for c in ArticleFake.__table__.constraints
        if isinstance(c, sa.CheckConstraint)
    ]
    assert len(check_constraints) >= 1
    sql_texts = [str(c.sqltext) for c in check_constraints]
    assert any("'pending'" in t and "'completed'" in t for t in sql_texts)


def test_article_fake_nullable_columns():
    cols = ArticleFake.__table__.c
    assert cols.title.nullable is True
    assert cols.description.nullable is True
    assert cols.model.nullable is True
    assert cols.temperature.nullable is True


def test_article_fake_no_extra_indexes():
    assert len(ArticleFake.__table__.indexes) == 0


def test_article_fake_relationship():
    assert hasattr(Article, "fake")
    assert Article.fake.property.mapper.class_ is ArticleFake


def test_article_back_ref():
    assert hasattr(ArticleFake, "article")
    assert ArticleFake.article.property.mapper.class_ is Article
