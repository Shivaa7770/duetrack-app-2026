import sqlite3
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from database import iso_now, new_id
from crypto_utils import (
    AUTH_COOKIE_NAME,
    COOKIE_MAX_AGE_SECONDS,
    compare_password,
    decrypt_password,
    hash_password,
    encrypt_password,
    sign_token,
)
from dependencies import get_current_user, get_db, require_role, to_user_dto
from models import (
    ChangePasswordRequest,
    CreateDealerRequest,
    LoginRequest,
    UpdateMeRequest,
    UserDTO,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

def find_main_dealer_id(conn: sqlite3.Connection) -> str | None:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE role = 'DEALER' ORDER BY created_at ASC LIMIT 1")
    row = cursor.fetchone()
    return row["id"] if row else None

@router.post("/login")
def login(payload: LoginRequest, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (payload.username.strip().lower(),))
    user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if user["status"] != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled. Contact your dealer.",
        )

    if not compare_password(payload.password, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = sign_token(user["id"], user["role"])
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return {"user": to_user_dto(user)}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        samesite="lax",
        httponly=True,
    )
    return {"message": "Logged out"}

@router.get("/me")
def me(current_user: sqlite3.Row = Depends(get_current_user)):
    return {"user": to_user_dto(current_user)}

@router.patch("/me")
def update_me(
    payload: UpdateMeRequest,
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    name = payload.name.strip()
    username = payload.username.strip().lower() if payload.username else current_user["username"]

    with conn:
        cursor.execute("UPDATE users SET name = ?, username = ? WHERE id = ?", (name, username, current_user["id"]))

    cursor.execute("SELECT * FROM users WHERE id = ?", (current_user["id"],))
    updated = cursor.fetchone()
    return {"user": to_user_dto(updated)}

@router.get("/me/password")
def get_my_password(
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT encrypted_password FROM users WHERE id = ?", (current_user["id"],))
    row = cursor.fetchone()
    if not row or not row["encrypted_password"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    plain = decrypt_password(row["encrypted_password"])
    return {"password": plain}

@router.patch("/me/password")
def change_my_password(
    payload: ChangePasswordRequest,
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if len(payload.newPassword) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    hashed = hash_password(payload.newPassword)
    encrypted = encrypt_password(payload.newPassword)

    cursor = conn.cursor()
    with conn:
        cursor.execute(
            "UPDATE users SET password = ?, encrypted_password = ? WHERE id = ?",
            (hashed, encrypted, current_user["id"]),
        )

    return {"message": "Password updated"}

@router.get("/dealers")
def get_dealers(
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = 'DEALER' ORDER BY created_at ASC")
    dealers = cursor.fetchall()
    main_dealer_id = find_main_dealer_id(conn)
    return {
        "dealers": [to_user_dto(d) for d in dealers],
        "isMainDealer": current_user["id"] == main_dealer_id,
    }

@router.post("/dealers", status_code=status.HTTP_201_CREATED)
def create_dealer(
    payload: CreateDealerRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    main_dealer_id = find_main_dealer_id(conn)
    if current_user["id"] != main_dealer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the main admin can create other admin accounts",
        )

    if len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (payload.username.strip().lower(),))
    if cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken")

    dealer_id = new_id()
    created_at = iso_now()
    hashed = hash_password(payload.password)
    encrypted = encrypt_password(payload.password)

    with conn:
        cursor.execute(
            """INSERT INTO users (id, name, username, phone, password, encrypted_password, role, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'DEALER', 'ACTIVE', ?)""",
            (dealer_id, payload.name.strip(), payload.username.strip().lower(), payload.phone.strip(), hashed, encrypted, created_at),
        )

    cursor.execute("SELECT * FROM users WHERE id = ?", (dealer_id,))
    new_dealer = cursor.fetchone()
    return {"user": to_user_dto(new_dealer)}

@router.delete("/dealers/{dealer_id}")
def delete_dealer(
    dealer_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    main_dealer_id = find_main_dealer_id(conn)
    if current_user["id"] != main_dealer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the main admin can delete other admin accounts",
        )
    if dealer_id == main_dealer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The main admin account cannot be deleted",
        )

    cursor = conn.cursor()
    with conn:
        cursor.execute("DELETE FROM users WHERE id = ? AND role = 'DEALER'", (dealer_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    return {"message": "Admin deleted"}
