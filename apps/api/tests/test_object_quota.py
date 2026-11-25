"""Quota violations map to safe, explicit errors while other SQL faults stay opaque."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from psycopg.errors import CheckViolation

from gc_database.storage import save_object


class QuotaExceeded(CheckViolation):
    @property
    def diag(self):
        return SimpleNamespace(constraint_name="gc_storage_total_quota")


class OtherConstraint(CheckViolation):
    @property
    def diag(self):
        return SimpleNamespace(constraint_name="object_exact_size")


def test_named_quota_maps_to_507_without_database_details():
    with patch("gc_database.storage.connection", side_effect=QuotaExceeded("private SQL details")):
        with pytest.raises(HTTPException) as error:
            save_object("example.txt", "text/plain", b"one byte")
    assert error.value.status_code == 507
    assert "SQL" not in error.value.detail
    assert "capacity" in error.value.detail


def test_other_database_constraints_are_not_misclassified():
    with patch("gc_database.storage.connection", side_effect=OtherConstraint("other constraint")):
        with pytest.raises(OtherConstraint):
            save_object("example.txt", "text/plain", b"one byte")
