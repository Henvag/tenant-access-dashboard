"""What start.sh does with the database, by the revision it finds."""

from app.preflight import DATABASE_AHEAD, MIGRATE, UP_TO_DATE, decide, script_directory


def test_head_revision_needs_nothing() -> None:
    script = script_directory()
    (head,) = script.get_heads()
    assert decide(head, script) == UP_TO_DATE


def test_older_revision_migrates() -> None:
    script = script_directory()
    (head,) = script.get_heads()
    older = script.get_revision(head).down_revision
    assert isinstance(older, str)
    assert decide(older, script) == MIGRATE


def test_empty_database_migrates() -> None:
    assert decide(None, script_directory()) == MIGRATE


def test_revision_from_a_newer_version_starts_without_migrating() -> None:
    # A newer version migrated the database and was then rolled back.
    assert decide("999_from_a_newer_version", script_directory()) == DATABASE_AHEAD
