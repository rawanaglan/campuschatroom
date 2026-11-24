import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


# --------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(
    os.getenv("DATABASE_PATH", str(BASE_DIR / "chatroom.db"))
)


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_connection():
    """
    Opens a connection to the SQLite database.
    Enables foreign key constraints.
    Returns the connection.
    """

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    # Enable foreign key relationships
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def init_db():
    """
    Creates all database tables if they do not exist.
    This function should run when the server starts.
    """

    connection = get_connection()

    try:
        connection.executescript("""

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS rooms (
                room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_by INTEGER,
                created_at TEXT NOT NULL,

                FOREIGN KEY (created_by)
                    REFERENCES users(user_id)
            );


            CREATE TABLE IF NOT EXISTS room_members (
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,

                PRIMARY KEY (room_id, user_id),

                FOREIGN KEY (room_id)
                    REFERENCES rooms(room_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL UNIQUE,
                sender_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,

                FOREIGN KEY (sender_id)
                    REFERENCES users(user_id),

                FOREIGN KEY (room_id)
                    REFERENCES rooms(room_id)
            );


            CREATE INDEX IF NOT EXISTS idx_messages_room_id
            ON messages(room_id, id);


            CREATE INDEX IF NOT EXISTS idx_messages_sender_id
            ON messages(sender_id);

        """)

        # Create the default room if it does not exist
        connection.execute("""
            INSERT OR IGNORE INTO rooms (
                room_name,
                created_by,
                created_at
            )
            VALUES (?, NULL, ?)
        """, ("general", datetime.now(timezone.utc).isoformat()))

        connection.commit()

    finally:
        connection.close()


# --------------------------------------------------
# USER OPERATIONS
# --------------------------------------------------

def register_user(username, password_hash):
    username = username.strip()

    if not username:
        raise ValueError("Username cannot be empty.")

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (
            username,
            password_hash,
            datetime.now(timezone.utc).isoformat()
        ))

        user_id = cursor.lastrowid

        # Automatically join the default room
        general_room = connection.execute("""
            SELECT room_id FROM rooms
            WHERE room_name = 'general'
        """).fetchone()

        if general_room:
            connection.execute("""
                INSERT INTO room_members (room_id, user_id, joined_at)
                VALUES (?, ?, ?)
            """, (
                general_room["room_id"],
                user_id,
                datetime.now(timezone.utc).isoformat()
            ))

        connection.commit()

        return get_user_by_id(user_id)

    except sqlite3.IntegrityError as error:
        connection.rollback()
        raise ValueError("Username already exists.") from error

    finally:
        connection.close()

def get_user_by_username(username):
    """
    Finds a user using their username.
    Used during login.
    """

    connection = get_connection()

    try:
        user = connection.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

        return dict(user) if user else None

    finally:
        connection.close()


def get_user_by_id(user_id):
    """
    Finds a user using their unique ID.
    """

    connection = get_connection()

    try:
        user = connection.execute("""
            SELECT user_id, username, created_at
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        return dict(user) if user else None

    finally:
        connection.close()


# --------------------------------------------------
# ROOM OPERATIONS
# --------------------------------------------------

def create_room(room_name, created_by):
    """
    Creates a new chat room.
    The creator is automatically added as a member.
    """

    room_name = room_name.strip()

    if not room_name:
        raise ValueError("Room name cannot be empty.")

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO rooms (
                room_name,
                created_by,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            room_name,
            created_by,
            datetime.now(timezone.utc).isoformat()
        ))

        room_id = cursor.lastrowid

        connection.execute("""
            INSERT INTO room_members (
                room_id,
                user_id,
                joined_at
            )
            VALUES (?, ?, ?)
        """, (
            room_id,
            created_by,
            datetime.now(timezone.utc).isoformat()
        ))

        connection.commit()

        return get_room_by_id(room_id)

    except sqlite3.IntegrityError as error:
        connection.rollback()
        raise ValueError("Room already exists or user does not exist.") from error

    finally:
        connection.close()


def get_room_by_id(room_id):
    """
    Retrieves a room using its ID.
    """

    connection = get_connection()

    try:
        room = connection.execute("""
            SELECT *
            FROM rooms
            WHERE room_id = ?
        """, (room_id,)).fetchone()

        return dict(room) if room else None

    finally:
        connection.close()


def add_room_member(room_id, user_id):
    """
    Adds a user to a chat room.
    """

    connection = get_connection()

    try:
        connection.execute("""
            INSERT OR IGNORE INTO room_members (
                room_id,
                user_id,
                joined_at
            )
            VALUES (?, ?, ?)
        """, (
            room_id,
            user_id,
            datetime.now(timezone.utc).isoformat()
        ))

        connection.commit()

        return True

    except sqlite3.IntegrityError:
        connection.rollback()
        raise ValueError("Room or user does not exist.")

    finally:
        connection.close()


def get_rooms(user_id=None):
    """
    Retrieves all rooms, or only rooms belonging to a user.
    """

    connection = get_connection()

    try:
        if user_id is None:
            rooms = connection.execute("""
                SELECT *
                FROM rooms
                ORDER BY room_id
            """).fetchall()

        else:
            rooms = connection.execute("""
                SELECT rooms.*
                FROM rooms
                JOIN room_members
                ON rooms.room_id = room_members.room_id
                WHERE room_members.user_id = ?
                ORDER BY rooms.room_id
            """, (user_id,)).fetchall()

        return [dict(room) for room in rooms]

    finally:
        connection.close()


# --------------------------------------------------
# MESSAGE OPERATIONS
# --------------------------------------------------

def save_message(client_id, sender_id, room_id, content):
    """
    Stores a message permanently.

    client_id is generated by the client and must be
    reused when retrying an unconfirmed message.

    Returns:
        message: Stored message information.
        created: True if inserted, False if already stored.
    """

    if not client_id or not content.strip():
        raise ValueError("Message ID and content are required.")

    connection = get_connection()

    try:
        # Ensure the sender belongs to the room
        membership = connection.execute("""
            SELECT 1
            FROM room_members
            WHERE room_id = ? AND user_id = ?
        """, (room_id, sender_id)).fetchone()

        if not membership:
            raise ValueError("Sender is not a member of this room.")

        existing = connection.execute("""
            SELECT *
            FROM messages
            WHERE client_id = ?
        """, (client_id,)).fetchone()

        if existing:
            existing = dict(existing)

            # A client ID cannot be reused for a different message
            if (
                existing["sender_id"] != sender_id
                or existing["room_id"] != room_id
                or existing["content"] != content
            ):
                raise ValueError("Message ID was already used.")

            return {
                "message": existing,
                "created": False
            }

        cursor = connection.execute("""
            INSERT INTO messages (
                client_id,
                sender_id,
                room_id,
                content,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            client_id,
            sender_id,
            room_id,
            content,
            datetime.now(timezone.utc).isoformat()
        ))

        message_id = cursor.lastrowid

        connection.commit()

        message = connection.execute("""
            SELECT *
            FROM messages
            WHERE id = ?
        """, (message_id,)).fetchone()

        return {
            "message": dict(message),
            "created": True
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_messages(room_id, last_seen=0, limit=100):
    """
    Retrieves messages after the last received message ID.

    last_seen prevents clients from downloading
    messages they have already received.

    limit controls the maximum number of messages returned.
    """

    if last_seen < 0:
        raise ValueError("last_seen cannot be negative.")

    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

    connection = get_connection()

    try:
        messages = connection.execute("""
            SELECT
                messages.id,
                messages.client_id,
                messages.sender_id,
                users.username AS sender,
                messages.room_id,
                messages.content,
                messages.timestamp

            FROM messages

            JOIN users
            ON messages.sender_id = users.user_id

            WHERE messages.room_id = ?
            AND messages.id > ?

            ORDER BY messages.id ASC

            LIMIT ?
        """, (room_id, last_seen, limit)).fetchall()

        return [dict(message) for message in messages]

    finally:
        connection.close()