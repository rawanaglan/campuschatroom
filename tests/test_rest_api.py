
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.rest_api import router
from server.db import init_db


# Create a separate FastAPI application for testing.
app = FastAPI()

app.include_router(router)

client = TestClient(app)


# Initialize the database before running tests.
@pytest.fixture(autouse=True)
def setup_database(tmp_path, monkeypatch):

    import server.db as db

    # Use a temporary database for every test.
    monkeypatch.setattr(
        db,
        "DB_PATH",
        tmp_path / "test_chatroom.db"
    )

    init_db()


# ==========================================
# 1. TEST REGISTRATION
# ==========================================

def test_register_user():

    response = client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["message"] == "Registration successful."
    assert data["user"]["username"] == "rawan123"
    assert "access_token" in data


# ==========================================
# 2. TEST DUPLICATE REGISTRATION
# ==========================================

def test_duplicate_registration():

    client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "different123"
        }
    )

    assert response.status_code == 409


# ==========================================
# 3. TEST LOGIN
# ==========================================

def test_login():

    client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/login",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Login successful."
    assert "access_token" in data


# ==========================================
# 4. TEST WRONG PASSWORD
# ==========================================

def test_wrong_password():

    client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/login",
        json={
            "username": "rawan123",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401


# ==========================================
# 5. TEST PROTECTED ROUTE
# ==========================================

def test_rooms_without_token():

    response = client.get("/api/rooms")

    assert response.status_code == 401


# ==========================================
# 6. TEST GET ROOMS
# ==========================================

def test_get_rooms():

    registration = client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    token = registration.json()["access_token"]

    response = client.get(
        "/api/rooms",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    rooms = response.json()["rooms"]

    assert len(rooms) >= 1
    assert any(room["room_name"] == "general" for room in rooms)


# ==========================================
# 7. TEST SEND MESSAGE
# ==========================================

def test_send_message():

    registration = client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    token = registration.json()["access_token"]

    # Get the general room ID.
    rooms = client.get(
        "/api/rooms",
        headers={
            "Authorization": f"Bearer {token}"
        }
    ).json()["rooms"]

    room_id = rooms[0]["room_id"]

    response = client.post(
        "/api/messages",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "client_id": "message-001",
            "room_id": room_id,
            "content": "Hello everyone!"
        }
    )

    assert response.status_code == 201
    assert response.json()["message"]["content"] == "Hello everyone!"


# ==========================================
# 8. TEST GET MESSAGE HISTORY
# ==========================================

def test_get_message_history():

    registration = client.post(
        "/api/register",
        json={
            "username": "rawan123",
            "password": "password123"
        }
    )

    token = registration.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    rooms = client.get(
        "/api/rooms",
        headers=headers
    ).json()["rooms"]

    room_id = rooms[0]["room_id"]

    # Send a message first.
    client.post(
        "/api/messages",
        headers=headers,
        json={
            "client_id": "message-002",
            "room_id": room_id,
            "content": "Testing history!"
        }
    )

    # Retrieve message history.
    response = client.get(
        "/api/messages",
        params={
            "room_id": room_id,
            "last_seen": 0
        },
        headers=headers
    )

    assert response.status_code == 200

    messages = response.json()["messages"]

    assert len(messages) == 1
    assert messages[0]["content"] == "Testing history!"
