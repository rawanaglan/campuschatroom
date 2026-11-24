
import pytest
from server import db


# Give every test its own temporary database.
# This prevents tests from changing your actual chatroom.db.
@pytest.fixture
def setup_database(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_chatroom.db"

    monkeypatch.setattr(db, "DB_PATH", test_db_path)

    db.init_db()

    return db


# TEST 1: Database creates the default general room.
def test_database_initialization(setup_database):
    rooms = setup_database.get_rooms()

    assert len(rooms) == 1
    assert rooms[0]["room_name"] == "general"


# TEST 2: A user can register successfully.
def test_register_user(setup_database):
    user = setup_database.register_user(
        "rawan",
        "hashed_password_example"
    )

    assert user is not None
    assert user["username"] == "rawan"


# TEST 3: Two users cannot register with the same username.
def test_duplicate_username(setup_database):
    setup_database.register_user("rawan", "hash1")

    with pytest.raises(ValueError):
        setup_database.register_user("rawan", "hash2")


# TEST 4: A newly registered user joins the general room.
def test_user_joins_general_room(setup_database):
    user = setup_database.register_user("rawan", "hash1")

    rooms = setup_database.get_rooms(user["user_id"])

    assert len(rooms) == 1
    assert rooms[0]["room_name"] == "general"


# TEST 5: A user can create a room.
def test_create_room(setup_database):
    user = setup_database.register_user("rawan", "hash1")

    room = setup_database.create_room(
        "gaming",
        user["user_id"]
    )

    assert room["room_name"] == "gaming"


# TEST 6: A message can be saved and retrieved.
def test_save_message(setup_database):
    user = setup_database.register_user("rawan", "hash1")
    rooms = setup_database.get_rooms(user["user_id"])
    general_room = rooms[0]

    result = setup_database.save_message(
        "message-001",
        user["user_id"],
        general_room["room_id"],
        "Hello everyone!"
    )

    assert result["created"] is True
    assert result["message"]["content"] == "Hello everyone!"


# TEST 7: Retrying the same message does not create a duplicate.
def test_duplicate_message(setup_database):
    user = setup_database.register_user("rawan", "hash1")
    room = setup_database.get_rooms(user["user_id"])[0]

    first_result = setup_database.save_message(
        "message-001",
        user["user_id"],
        room["room_id"],
        "Hello!"
    )

    second_result = setup_database.save_message(
        "message-001",
        user["user_id"],
        room["room_id"],
        "Hello!"
    )

    assert first_result["created"] is True
    assert second_result["created"] is False
    assert first_result["message"]["id"] == second_result["message"]["id"]


# TEST 8: Message history supports last_seen pagination.
def test_get_messages_after_last_seen(setup_database):
    user = setup_database.register_user("rawan", "hash1")
    room = setup_database.get_rooms(user["user_id"])[0]

    setup_database.save_message(
        "message-001", user["user_id"], room["room_id"], "First"
    )

    setup_database.save_message(
        "message-002", user["user_id"], room["room_id"], "Second"
    )

    messages = setup_database.get_messages(
        room["room_id"],
        last_seen=1
    )

    assert len(messages) == 1
    assert messages[0]["content"] == "Second"
