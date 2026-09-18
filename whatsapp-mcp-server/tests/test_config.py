"""The store paths and bridge URL must be overridable by environment variable.

Running the MCP server in a container relies on this: the bridge is a different
host, and its store is mounted somewhere other than a sibling checkout. These
are read at import time, so each case reloads the module.
"""
import importlib

import whatsapp


def _reload(monkeypatch, **env):
    for key in (
        "WHATSAPP_STORE_DIR",
        "WHATSAPP_MESSAGES_DB",
        "WHATSAPP_SESSION_DB",
        "WHATSAPP_API_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(whatsapp)


def test_defaults_point_at_a_sibling_bridge_checkout(monkeypatch):
    mod = _reload(monkeypatch)
    assert mod.MESSAGES_DB_PATH.endswith("whatsapp-bridge/store/messages.db")
    assert mod.WHATSAPP_DB_PATH.endswith("whatsapp-bridge/store/whatsapp.db")
    assert mod.WHATSAPP_API_BASE_URL == "http://localhost:8080/api"


def test_store_dir_relocates_both_databases(monkeypatch):
    mod = _reload(monkeypatch, WHATSAPP_STORE_DIR="/data/store")
    assert mod.MESSAGES_DB_PATH == "/data/store/messages.db"
    assert mod.WHATSAPP_DB_PATH == "/data/store/whatsapp.db"


def test_individual_database_paths_win_over_the_store_dir(monkeypatch):
    mod = _reload(
        monkeypatch,
        WHATSAPP_STORE_DIR="/data/store",
        WHATSAPP_MESSAGES_DB="/elsewhere/m.db",
        WHATSAPP_SESSION_DB="/elsewhere/s.db",
    )
    assert mod.MESSAGES_DB_PATH == "/elsewhere/m.db"
    assert mod.WHATSAPP_DB_PATH == "/elsewhere/s.db"


def test_api_base_url_is_overridable(monkeypatch):
    mod = _reload(monkeypatch, WHATSAPP_API_BASE_URL="http://whatsapp-bridge:8080/api")
    assert mod.WHATSAPP_API_BASE_URL == "http://whatsapp-bridge:8080/api"


def test_api_base_url_tolerates_a_trailing_slash(monkeypatch):
    """Requests are built as f"{WHATSAPP_API_BASE_URL}/send", so a trailing
    slash would otherwise produce a double slash in the path."""
    mod = _reload(monkeypatch, WHATSAPP_API_BASE_URL="http://whatsapp-bridge:8080/api/")
    assert mod.WHATSAPP_API_BASE_URL == "http://whatsapp-bridge:8080/api"


def test_module_is_left_at_its_defaults(monkeypatch):
    """Guard against these reloads leaking into the rest of the suite."""
    _reload(monkeypatch)
    assert whatsapp.WHATSAPP_API_BASE_URL == "http://localhost:8080/api"
