"""Regression tests for list_chats / get_chat and the include_last_message flag.

Uses a synthetic SQLite database with fabricated JIDs and message content.
"""
import sqlite3

import pytest

import whatsapp

ALICE = "111111@s.whatsapp.net"
GROUP = "120363111111@g.us"


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """Synthetic messages.db pointed to by whatsapp.MESSAGES_DB_PATH."""
    path = tmp_path / "messages.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP);
        CREATE TABLE messages (
            id TEXT, chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP,
            is_from_me BOOLEAN, media_type TEXT, PRIMARY KEY (id, chat_jid)
        );
        """
    )
    conn.executemany(
        "INSERT INTO chats VALUES (?,?,?)",
        [
            (ALICE, "Alice", "2026-01-01T10:00:00"),
            (GROUP, "Hiking Group", "2026-01-01T12:00:00"),
        ],
    )
    conn.executemany(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
        [
            ("m_alice", ALICE, ALICE, "hello there", "2026-01-01T10:00:00", 0, None),
            ("m_group", GROUP, ALICE, "see you sunday", "2026-01-01T12:00:00", 0, None),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(whatsapp, "MESSAGES_DB_PATH", str(path))
    return path


# --- list_chats -----------------------------------------------------------

def test_list_chats_with_last_message_includes_content():
    chats = whatsapp.list_chats(include_last_message=True)
    assert {c.jid for c in chats} == {ALICE, GROUP}
    assert {c.last_message for c in chats} == {"hello there", "see you sunday"}


def test_list_chats_without_last_message_still_returns_chats():
    chats = whatsapp.list_chats(include_last_message=False)
    assert {c.jid for c in chats} == {ALICE, GROUP}
    assert all(c.last_message is None for c in chats)


def test_list_chats_returns_same_chats_regardless_of_include_last_message():
    with_msg = [c.jid for c in whatsapp.list_chats(include_last_message=True)]
    without = [c.jid for c in whatsapp.list_chats(include_last_message=False)]
    assert with_msg == without


# --- get_chat -------------------------------------------------------------

def test_get_chat_with_last_message_includes_content():
    chat = whatsapp.get_chat(ALICE, include_last_message=True)
    assert chat is not None
    assert chat.last_message == "hello there"


def test_get_chat_without_last_message_still_returns_chat():
    chat = whatsapp.get_chat(ALICE, include_last_message=False)
    assert chat is not None
    assert chat.jid == ALICE
    assert chat.name == "Alice"
    assert chat.last_message is None


# --- latest-message join ---------------------------------------------------

def test_last_message_is_the_newest_even_when_chat_timestamp_drifts(db):
    """chats.last_message_time and messages.timestamp can disagree.

    The old join matched them for equality, so a chat whose recorded
    last_message_time had drifted away from any actual message row silently
    lost its last_message.
    """
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
        ("m_alice2", ALICE, ALICE, "newest", "2026-01-01T11:00:00", 0, None),
    )
    # Drift the chat's recorded time away from every message timestamp.
    conn.execute(
        "UPDATE chats SET last_message_time = ? WHERE jid = ?",
        ("2026-01-01T11:00:30", ALICE),
    )
    conn.commit()
    conn.close()

    chat = whatsapp.get_chat(ALICE)
    assert chat is not None
    assert chat.last_message == "newest"

    by_jid = {c.jid: c for c in whatsapp.list_chats()}
    assert by_jid[ALICE].last_message == "newest"


def test_chat_is_not_duplicated_when_two_messages_share_a_timestamp(db):
    """The equality join returned one row per timestamp-matching message."""
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
        ("m_alice_tie", ALICE, ALICE, "tied", "2026-01-01T10:00:00", 0, None),
    )
    conn.commit()
    conn.close()

    jids = [c.jid for c in whatsapp.list_chats()]
    assert jids.count(ALICE) == 1


# --- LID-keyed direct chats ------------------------------------------------

def test_get_direct_chat_by_contact_finds_a_lid_keyed_chat(tmp_path, monkeypatch):
    """A direct chat can be keyed by LID, so the phone number never appears
    in chats.jid. The mapping lives in the bridge's whatsmeow session store."""
    lid_jid = "99887766@lid"
    phone = "111111"

    messages_db = tmp_path / "lid_messages.db"
    conn = sqlite3.connect(messages_db)
    conn.executescript(
        """
        CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP);
        CREATE TABLE messages (
            id TEXT, chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP,
            is_from_me BOOLEAN, media_type TEXT, PRIMARY KEY (id, chat_jid)
        );
        """
    )
    conn.execute("INSERT INTO chats VALUES (?,?,?)", (lid_jid, "Alice", "2026-01-01T10:00:00"))
    conn.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
        ("m1", lid_jid, lid_jid, "hi from a lid chat", "2026-01-01T10:00:00", 0, None),
    )
    conn.commit()
    conn.close()

    session_db = tmp_path / "lid_whatsapp.db"
    conn = sqlite3.connect(session_db)
    conn.execute("CREATE TABLE whatsmeow_lid_map (lid TEXT, pn TEXT)")
    conn.execute("INSERT INTO whatsmeow_lid_map VALUES (?,?)", (lid_jid, f"{phone}@s.whatsapp.net"))
    conn.commit()
    conn.close()

    monkeypatch.setattr(whatsapp, "MESSAGES_DB_PATH", str(messages_db))
    monkeypatch.setattr(whatsapp, "WHATSAPP_DB_PATH", str(session_db))

    chat = whatsapp.get_direct_chat_by_contact(phone)
    assert chat is not None
    assert chat.jid == lid_jid
    assert chat.last_message == "hi from a lid chat"


def test_lid_lookup_degrades_when_the_session_store_is_missing(tmp_path, monkeypatch):
    """No whatsapp.db (bridge never run) must not raise — just no LID matches."""
    monkeypatch.setattr(whatsapp, "WHATSAPP_DB_PATH", str(tmp_path / "absent.db"))
    assert whatsapp._lids_for_phone("111111") == []
    # The phone-JID path still works.
    assert whatsapp.get_direct_chat_by_contact("111111").jid == ALICE
