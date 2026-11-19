from app.config import settings
from app.modules.auth import service


def test_empty_allowlist_allows_any_verified_account(monkeypatch):
    monkeypatch.setattr(settings, "allowed_google_emails", "")
    assert service._is_allowed("anyone@example.com")


def test_allowlist_is_enforced_and_case_insensitive(monkeypatch):
    monkeypatch.setattr(settings, "allowed_google_emails", "owner@example.com, Second@Example.com ")
    assert service._is_allowed("owner@example.com")
    assert service._is_allowed("SECOND@example.com")
    assert not service._is_allowed("stranger@example.com")


def test_blank_entries_are_ignored(monkeypatch):
    monkeypatch.setattr(settings, "allowed_google_emails", " , owner@example.com , ")
    assert service._is_allowed("owner@example.com")
    assert not service._is_allowed("stranger@example.com")
