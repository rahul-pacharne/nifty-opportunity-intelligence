from pathlib import Path

from app.runtime.persistence import MIGRATIONS_DIR, split_sql


def test_migration_files_split_into_single_statements() -> None:
    paths = sorted(Path(MIGRATIONS_DIR).glob("*.sql"))
    assert [path.name for path in paths] == [
        "001_market_observations.sql",
        "002_runtime_persistence.sql",
    ]
    for path in paths:
        statements = split_sql(path.read_text(encoding="utf-8"))
        assert len(statements) >= 5
        for statement in statements:
            assert not statement.startswith("--")
            assert ";" not in statement
            assert statement
