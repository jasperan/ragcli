"""Guards for the raw-SQL command in the db CLI.

.audit/SECURITY.md (generation 1, LOW-2) recorded that the "Only SELECT queries are allowed"
check was a prefix test, so a second statement could ride along behind a SELECT. These tests
pin the tightened behaviour; they need no database because the guard is pure.
"""
import pytest

from ragcli.cli.commands.db import _is_single_select


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 FROM dual",
        "select * from documents",
        "  SELECT id FROM chunks ;  ",
        "SELECT\n  id\nFROM chunks",
    ],
)
def test_accepts_a_single_select(sql):
    assert _is_single_select(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 FROM dual; DROP TABLE users",
        "SELECT 1; SELECT 2",
        "DROP TABLE users",
        "DELETE FROM documents",
        "",
        "SELECT",
        "  ; SELECT 1",
    ],
)
def test_rejects_anything_that_is_not_one_select(sql):
    assert not _is_single_select(sql)
