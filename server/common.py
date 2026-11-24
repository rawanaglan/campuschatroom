
import os
import json
import time
import hmac
import hashlib
import secrets
import base64

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from server.db import get_user_by_id


# ==========================================
# 1. PASSWORD SECURITY
# ==========================================

def hash_password(password: str) -> str:
    """
    Hash a password using scrypt and a random salt.
    The salt is stored together with the hash.
    """

    salt = secrets.token_bytes(16)

    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64
    )

    # Store the algorithm, salt, and hash together.
    return f"scrypt${salt.hex()}${password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Check whether the entered password matches the stored hash.
    """

    try:
        algorithm, salt_hex, hash_hex = stored_hash.split("$")

        if algorithm != "scrypt":
            return False

        salt = bytes.fromhex(salt_hex)
        original_hash = bytes.fromhex(hash_hex)

        new_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=64
        )

        # Compare safely to avoid timing-based attacks.
        return hmac.compare_digest(new_hash, original_hash)

    except (ValueError, TypeError):
        return False


# ==========================================
# 2. AUTHENTICATION TOKENS
# ==========================================

SECRET_KEY = os.getenv(
    "CHAT_SECRET_KEY",
    "development-secret-change-this-before-deployment"
)

TOKEN_EXPIRY_SECONDS = 24 * 60 * 60


def encode_base64(data: bytes) -> str:
    """Convert bytes into URL-safe Base64 text."""

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def decode_base64(data: str) -> bytes:
    """Convert URL-safe Base64 text back into bytes."""

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user_id: int, username: str) -> str:
    """
    Create a signed token for an authenticated user.
    The token expires after 24 hours.
    """

    payload = {
        "user_id": user_id,
        "username": username,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    encoded_payload = encode_base64(payload_bytes)

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256
    ).digest()

    encoded_signature = encode_base64(signature)

    return f"{encoded_payload}.{encoded_signature}"


def decode_access_token(token: str):
    """
    Verify a token and return its information.
    Return None if the token is invalid or expired.
    """

    try:
        encoded_payload, encoded_signature = token.split(".")

        expected_signature = hmac.new(
            SECRET_KEY.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256
        ).digest()

        actual_signature = decode_base64(encoded_signature)

        if not hmac.compare_digest(expected_signature, actual_signature):
            return None

        payload_bytes = decode_base64(encoded_payload)
        payload = json.loads(payload_bytes)

        if payload["exp"] < int(time.time()):
            return None

        if not isinstance(payload["user_id"], int):
            return None

        return payload

    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


# ==========================================
# 3. AUTHENTICATION FOR REST ENDPOINTS
# ==========================================

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    FastAPI dependency that checks the user's token
    and returns their database information.
    """

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required."
        )

    payload = decode_access_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token."
        )

    user = get_user_by_id(payload["user_id"])

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found."
        )

    return user
