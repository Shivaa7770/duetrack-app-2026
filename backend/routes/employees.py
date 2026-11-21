import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from database import iso_now, new_id
from crypto_utils import decrypt_password, encrypt_password, hash_password
from dependencies import (
    get_db,
    require_role,
    to_user_dto,
)
from models import (
    CreateEmployeeRequest,
    EmployeePerformanceDTO,
    UpdateEmployeeRequest,
    UserDTO,
)

router = APIRouter(prefix="/api/employees", tags=["employees"])

@router.get("")
def list_employees(
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = 'EMPLOYEE' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    return {"employees": [to_user_dto(r) for r in rows]}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: CreateEmployeeRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    if len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (payload.username.strip().lower(),))
    if cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken")

    emp_id = new_id()
    created_at = iso_now()
    hashed = hash_password(payload.password)
    encrypted = encrypt_password(payload.password)

    with conn:
        cursor.execute(
            """INSERT INTO users (id, name, username, phone, password, encrypted_password, role, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'EMPLOYEE', 'ACTIVE', ?)""",
            (emp_id, payload.name.strip(), payload.username.strip().lower(), payload.phone.strip(), hashed, encrypted, created_at),
        )

    cursor.execute("SELECT * FROM users WHERE id = ?", (emp_id,))
    row = cursor.fetchone()
    return {"employee": to_user_dto(row)}

@router.get("/{employee_id}")
def get_employee(
    employee_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ? AND role = 'EMPLOYEE'", (employee_id,))
    emp_row = cursor.fetchone()
    if not emp_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    cursor.execute("SELECT * FROM collections WHERE assigned_employee_id = ?", (employee_id,))
    cols = cursor.fetchall()

    total_assigned = 0.0
    total_collected = 0.0
    pending_count = 0
    partially_collected_count = 0
    completed_count = 0

    for c in cols:
        total_assigned += float(c["total_amount"])
        total_collected += float(c["received_amount"])
        if c["status"] == "PENDING":
            pending_count += 1
        elif c["status"] == "PARTIALLY_COLLECTED":
            partially_collected_count += 1
        else:
            completed_count += 1

    performance = EmployeePerformanceDTO(
        totalAssigned=total_assigned,
        totalCollected=total_collected,
        pendingCount=pending_count,
        partiallyCollectedCount=partially_collected_count,
        completedCount=completed_count,
    )

    return {
        "employee": to_user_dto(emp_row),
        "performance": performance.model_dump(by_alias=True),
    }

@router.get("/{employee_id}/password")
def get_employee_password(
    employee_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT encrypted_password FROM users WHERE id = ? AND role = 'EMPLOYEE'", (employee_id,))
    row = cursor.fetchone()
    if not row or not row["encrypted_password"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    plain = decrypt_password(row["encrypted_password"])
    return {"password": plain}

@router.patch("/{employee_id}")
def update_employee(
    employee_id: str,
    payload: UpdateEmployeeRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ? AND role = 'EMPLOYEE'", (employee_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    sets = []
    values = []

    if payload.name is not None:
        sets.append("name = ?")
        values.append(payload.name.strip())
    if payload.phone is not None:
        sets.append("phone = ?")
        values.append(payload.phone.strip())
    if payload.username is not None:
        new_username = payload.username.strip().lower()
        cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (new_username, employee_id))
        if cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken")
        sets.append("username = ?")
        values.append(new_username)
    if payload.password:
        if len(payload.password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
        sets.append("password = ?")
        values.append(hash_password(payload.password))
        sets.append("encrypted_password = ?")
        values.append(encrypt_password(payload.password))

    if sets:
        values.append(employee_id)
        with conn:
            cursor.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", values)

    cursor.execute("SELECT * FROM users WHERE id = ?", (employee_id,))
    updated = cursor.fetchone()
    return {"employee": to_user_dto(updated)}

@router.delete("/{employee_id}")
def delete_employee(
    employee_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS count FROM collections WHERE assigned_employee_id = ? AND status != 'COMPLETED'",
        (employee_id,),
    )
    active_count = cursor.fetchone()["count"]
    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an employee with pending or partially collected collections — reassign them first.",
        )

    with conn:
        cursor.execute("DELETE FROM users WHERE id = ? AND role = 'EMPLOYEE'", (employee_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    return {"message": "Employee deleted"}
