from app.config import Settings


def test_neon_url_is_made_asyncpg_compatible():
    url = Settings(
        database_url="postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    ).database_url
    assert url == "postgresql+asyncpg://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?ssl=require"


def test_render_style_url_unchanged_apart_from_driver():
    url = Settings(database_url="postgres://u:p@host:5432/db").database_url
    assert url == "postgresql+asyncpg://u:p@host:5432/db"
