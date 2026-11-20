import os
import pytest
from fastapi import HTTPException
from gc_database.security import check_identifier, check_schema, require_admin, require_configuration


def test_good_identifier():
    assert check_identifier("customer_records") == "customer_records"


@pytest.mark.parametrize("unsafe", [";drop table", "foo.bar", "a b", "__A", "1table", "x" * 64])
def test_reject_sql_identifiers(unsafe):
    with pytest.raises(HTTPException):
        check_identifier(unsafe)


def test_schema_is_allowlisted():
    with pytest.raises(HTTPException) as exc:
        check_schema("pg_catalog")
    assert exc.value.status_code == 404


def test_fail_closed_without_admin_secret(monkeypatch):
    monkeypatch.delenv("GC_ADMIN_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        require_configuration()


def test_constant_time_token_check(monkeypatch):
    monkeypatch.setenv("GC_ADMIN_TOKEN", "S" * 48)
    for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"):
        monkeypatch.setenv(key, "test")
    require_admin("Bearer " + "S" * 48)
    with pytest.raises(HTTPException) as exc:
        require_admin("Bearer " + "X" * 48)
    assert exc.value.status_code == 401
