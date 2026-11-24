
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from server.db import (
    register_user,
    get_user_by_username,
    get_rooms,
    save_message,
    get_messages
)

from server.common import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)


# ==========================================
# 1. CREATE THE API ROUTER
# ==========================================

router = APIRouter(
    prefix="/api",
    tags=["REST API"]
)


# ==========================================
# 2. REQUEST DATA MODELS
# ==========================================

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class MessageRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    room_id: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=5000)


# ==========================================
# 3. HELPER FUNCTION
# ==========================================

def check_room_membership(user_id: int, room_id: int):
    """
    Check whether a user belongs to a specific room.
    """

    user_rooms = get_rooms(user_id)

    for room in user_rooms:
        if room["room_id"] == room_id:
            return True

    return False


# ==========================================
# 4. USER REGISTRATION
# ==========================================

@router.post("/register", status_code=201)
def register(request: RegisterRequest):

    username = request.username.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must contain at least 3 non-space characters."
        )

    if not request.password.strip():
        raise HTTPException(
            status_code=400,
            detail="Password cannot be empty."
        )

    # Hash the password before storing it.
    password_hash = hash_password(request.password)

    try:
        user = register_user(username, password_hash)

    except ValueError:
        raise HTTPException(
            status_code=409,
            detail="Username already exists."
        )

    # Create a login token for the new user.
    token = create_access_token(
        user["user_id"],
        user["username"]
    )

    return {
        "message": "Registration successful.",
        "user": user,
        "access_token": token,
        "token_type": "bearer"
    }


# ==========================================
# 5. USER LOGIN
# ==========================================

@router.post("/login")
def login(request: LoginRequest):

    username = request.username.strip()

    # Find the user in the database.
    user = get_user_by_username(username)

    # Check the entered password.
    if user is None or not verify_password(
        request.password,
        user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )

    # Generate a token after successful login.
    token = create_access_token(
        user["user_id"],
        user["username"]
    )

    return {
        "message": "Login successful.",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"]
        },
        "access_token": token,
        "token_type": "bearer"
    }


# ==========================================
# 6. GET USER ROOMS
# ==========================================

@router.get("/rooms")
def retrieve_rooms(
    current_user: dict = Depends(get_current_user)
):

    rooms = get_rooms(current_user["user_id"])

    return {
        "rooms": rooms
    }


# ==========================================
# 7. SEND A MESSAGE
# ==========================================

@router.post("/messages", status_code=201)
def send_message(
    request: MessageRequest,
    current_user: dict = Depends(get_current_user)
):

    if not request.content.strip():
        raise HTTPException(
            status_code=400,
            detail="Message content cannot be empty."
        )

    user_id = current_user["user_id"]

    # Make sure the user belongs to this room.
    if not check_room_membership(user_id, request.room_id):
        raise HTTPException(
            status_code=403,
            detail="You are not a member of this room."
        )

    try:
        result = save_message(
            client_id=request.client_id,
            sender_id=user_id,
            room_id=request.room_id,
            content=request.content.strip()
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "message": result["message"],
        "created": result["created"]
    }


# ==========================================
# 8. GET MESSAGE HISTORY
# ==========================================

@router.get("/messages")
def retrieve_messages(
    room_id: int = Query(gt=0),
    last_seen: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["user_id"]

    # Make sure the user can access this room.
    if not check_room_membership(user_id, room_id):
        raise HTTPException(
            status_code=403,
            detail="You are not a member of this room."
        )

    messages = get_messages(
        room_id=room_id,
        last_seen=last_seen,
        limit=limit
    )

    return {
        "messages": messages,
        "last_seen": last_seen,
        "count": len(messages)
    }

