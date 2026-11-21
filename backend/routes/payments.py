from datetime import datetime, timezone
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from database import iso_now, new_id
from crypto_utils import compute_status
from dependencies import (
    get_current_user,
    get_db,
    require_role,
    to_payment_dto,
)
from models import (
    CreatePaymentRequest,
    PaymentDTO,
    UpdatePaymentRequest,
    VerifyPaymentRequest,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])

REF_JOIN_SELECT = """
SELECT
    p.*,
    cl.id AS cl_id, cl.name AS cl_name, cl.phone AS cl_phone, cl.address AS cl_address, cl.notes AS cl_notes, cl.created_by AS cl_created_by, cl.created_at AS cl_created_at,
    u.id AS u_id, u.name AS u_name, u.username AS u_username, u.phone AS u_phone, u.role AS u_role, u.status AS u_status, u.created_at AS u_created_at
FROM payments p
LEFT JOIN clients cl ON cl.id = p.client_id
LEFT JOIN users u ON u.id = p.employee_id
"""

def map_joined_payment(r: sqlite3.Row) -> PaymentDTO:
    client_row = None
    if r["cl_id"]:
        client_row = {
            "id": r["cl_id"],
            "name": r["cl_name"],
            "phone": r["cl_phone"],
            "address": r["cl_address"],
            "notes": r["cl_notes"],
            "created_by": r["cl_created_by"],
            "created_at": r["cl_created_at"],
        }
    emp_row = None
    if r["u_id"]:
        emp_row = {
            "id": r["u_id"],
            "name": r["u_name"],
            "username": r["u_username"],
            "phone": r["u_phone"],
            "role": r["u_role"],
            "status": r["u_status"],
            "created_at": r["u_created_at"],
        }
    return to_payment_dto(r, client_row, emp_row)

def resolve_payment_timestamp(date_str: str) -> str:
    # If date_str is already a full ISO string with time
    if "T" in date_str:
        return date_str
    now = datetime.now(timezone.utc)
    try:
        parts = [int(p) for p in date_str.split("-")]
        if len(parts) == 3:
            y, m, d = parts
            resolved = now.replace(year=y, month=m, day=d)
            return resolved.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except Exception:
        pass
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

@router.get("")
def list_payments(
    collection: Optional[str] = Query(None),
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    clauses = []
    values = []

    if collection:
        clauses.append("p.collection_id = ?")
        values.append(collection)

    if current_user["role"] == "EMPLOYEE":
        clauses.append("p.employee_id = ?")
        values.append(current_user["id"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"{REF_JOIN_SELECT} {where} ORDER BY p.created_at DESC"

    cursor = conn.cursor()
    cursor.execute(query, values)
    rows = cursor.fetchall()
    return {"payments": [map_joined_payment(r) for r in rows]}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: CreatePaymentRequest,
    current_user: sqlite3.Row = Depends(require_role("EMPLOYEE")),
    conn: sqlite3.Connection = Depends(get_db),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than 0")

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM collections WHERE id = ?", (payload.collection,))
    col = cursor.fetchone()
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if str(col["assigned_employee_id"]) != str(current_user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add payments to your own assigned collections",
        )

    if col["status"] == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This collection has already been fully collected",
        )

    rem = float(col["remaining_amount"])
    if payload.amount > rem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount cannot exceed the remaining balance of {rem}",
        )

    cursor.execute("SELECT * FROM clients WHERE id = ?", (col["client_id"],))
    client = cursor.fetchone()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    payment_id = new_id()
    now = iso_now()
    payment_date = resolve_payment_timestamp(payload.paymentDate)

    next_received = float(col["received_amount"]) + payload.amount
    next_remaining = float(col["remaining_amount"]) - payload.amount
    next_status = compute_status(float(col["total_amount"]), next_received)

    with conn:
        cursor.execute(
            """INSERT INTO payments (id, collection_id, client_id, employee_id, client_name, client_phone, employee_name, amount, payment_method, remarks, payment_date, created_at, verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                payment_id,
                col["id"],
                col["client_id"],
                current_user["id"],
                client["name"],
                client["phone"],
                current_user["name"],
                payload.amount,
                payload.paymentMethod,
                payload.remarks.strip() if payload.remarks else None,
                payment_date,
                now,
            ),
        )
        cursor.execute(
            """UPDATE collections
               SET received_amount = ?, remaining_amount = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (next_received, next_remaining, next_status, now, col["id"]),
        )

    cursor.execute(f"{REF_JOIN_SELECT} WHERE p.id = ?", (payment_id,))
    row = cursor.fetchone()
    return {"payment": map_joined_payment(row)}

@router.get("/{payment_id}")
def get_payment(
    payment_id: str,
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute(f"{REF_JOIN_SELECT} WHERE p.id = ?", (payment_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if current_user["role"] == "EMPLOYEE" and str(row["employee_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own payments")

    return {"payment": map_joined_payment(row)}

@router.patch("/{payment_id}")
def update_payment(
    payment_id: str,
    payload: UpdatePaymentRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than 0")

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    payment = cursor.fetchone()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if not payment["collection_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    cursor.execute("SELECT * FROM collections WHERE id = ?", (payment["collection_id"],))
    col = cursor.fetchone()
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    delta = payload.amount - float(payment["amount"])
    next_received = float(col["received_amount"]) + delta

    if next_received < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount cannot make the collected total negative")
    if next_received > float(col["total_amount"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount cannot exceed the collection's total of {col['total_amount']}",
        )

    next_remaining = float(col["total_amount"]) - next_received
    next_status = compute_status(float(col["total_amount"]), next_received)
    now = iso_now()

    payment_sets = ["amount = ?"]
    payment_values = [payload.amount]

    if payload.paymentMethod is not None:
        payment_sets.append("payment_method = ?")
        payment_values.append(payload.paymentMethod)
    if payload.remarks is not None:
        payment_sets.append("remarks = ?")
        payment_values.append(payload.remarks.strip() if payload.remarks else None)

    payment_values.append(payment_id)

    with conn:
        cursor.execute(f"UPDATE payments SET {', '.join(payment_sets)} WHERE id = ?", payment_values)
        cursor.execute(
            """UPDATE collections
               SET received_amount = ?, remaining_amount = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (next_received, next_remaining, next_status, now, col["id"]),
        )

    cursor.execute(f"{REF_JOIN_SELECT} WHERE p.id = ?", (payment_id,))
    row = cursor.fetchone()
    return {"payment": map_joined_payment(row)}

@router.patch("/{payment_id}/verify")
def verify_payment(
    payment_id: str,
    payload: VerifyPaymentRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM payments WHERE id = ?", (payment_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    with conn:
        cursor.execute("UPDATE payments SET verified = ? WHERE id = ?", (1 if payload.verified else 0, payment_id))

    cursor.execute(f"{REF_JOIN_SELECT} WHERE p.id = ?", (payment_id,))
    row = cursor.fetchone()
    return {"payment": map_joined_payment(row)}

@router.delete("/{payment_id}")
def delete_payment(
    payment_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    payment = cursor.fetchone()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    col = None
    if payment["collection_id"]:
        cursor.execute("SELECT * FROM collections WHERE id = ?", (payment["collection_id"],))
        col = cursor.fetchone()

    now = iso_now()
    with conn:
        if col:
            next_received = float(col["received_amount"]) - float(payment["amount"])
            next_remaining = float(col["remaining_amount"]) + float(payment["amount"])
            next_status = compute_status(float(col["total_amount"]), next_received)

            cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            cursor.execute(
                """UPDATE collections
                   SET received_amount = ?, remaining_amount = ?, status = ?, updated_at = ?
                   WHERE id = ?""",
                (next_received, next_remaining, next_status, now, col["id"]),
            )
        else:
            cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))

    return {"message": "Payment deleted"}
