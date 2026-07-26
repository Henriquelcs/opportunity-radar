from src.storage.database import Database


def test_database_creates_tables(tmp_path):
    database_path = (
        tmp_path / "test.db"
    )

    database = Database(database_path)

    database.initialize()

    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert "opportunities" in tables
    assert "collection_runs" in tables


def test_database_creates_parent_directory(
    tmp_path,
):
    database_path = (
        tmp_path
        / "nested"
        / "storage"
        / "test.db"
    )

    Database(database_path).initialize()

    assert database_path.exists()
