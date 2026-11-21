from datetime import datetime
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from database import iso_now, new_id
from crypto_utils import compute_status
from dependencies import (
    get_current_user,
    get_db,
    require_role,
    to_collection_dto,
)
from models import (
    CollectionDTO,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)

router = APIRouter(prefix="/api/collections", tags=["collections"])

REF_JOIN_SELECT = """
SELECT
    c.*,
    cl.id AS cl_id, cl.name AS cl_name, cl.phone AS cl_phone, cl.address AS cl_address, cl.notes AS cl_notes, cl.created_by AS cl_created_by, cl.created_at AS cl_created_at,
    u.id AS u_id, u.name AS u_name, u.username AS u_username, u.phone AS u_phone, u.role AS u_role, u.status AS u_status, u.created_at AS u_created_at
FROM collections c
LEFT JOIN clients cl ON cl.id = c.client_id
LEFT JOIN users u ON u.id = c.assigned_employee_id
"""

def map_joined_collection(r: sqlite3.Row) -> CollectionDTO:
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
    return to_collection_dto(r, client_row, emp_row)

@router.get("")
def list_collections(
    status_filter: Optional[str] = Query(None, alias="status"),
    employee: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    dateFrom: Optional[str] = Query(None),
    dateTo: Optional[str] = Query(None),
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    clauses = []
    values = []

    if current_user["role"] == "EMPLOYEE":
        clauses.append("c.assigned_employee_id = ?")
        values.append(current_user["id"])
    elif employee:
        clauses.append("c.assigned_employee_id = ?")
        values.append(employee)

    if status_filter:
        clauses.append("c.status = ?")
        values.append(status_filter)
    if client:
        clauses.append("c.client_id = ?")
        values.append(client)
    if dateFrom:
        clauses.append("c.collection_date >= ?")
        values.append(dateFrom)
    if dateTo:
        clauses.append("c.collection_date <= ?")
        values.append(dateTo)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"{REF_JOIN_SELECT} {where} ORDER BY c.created_at DESC"

    cursor = conn.cursor()
    cursor.execute(query, values)
    rows = cursor.fetchall()
    return {"collections": [map_joined_collection(r) for r in rows]}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CreateCollectionRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    if payload.totalAmount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Total amount must be greater than 0")

    try:
        dt_col = datetime.fromisoformat(payload.collectionDate.replace("Z", "+00:00"))
        dt_due = datetime.fromisoformat(payload.dueDate.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format")

    if dt_due <= dt_col:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Due date must be after the collection date")

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM clients WHERE id = ?", (payload.client,))
    if not cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    cursor.execute("SELECT id, status FROM users WHERE id = ? AND role = 'EMPLOYEE'", (payload.assignedEmployee,))
    emp = cursor.fetchone()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if emp["status"] != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign to an inactive employee")

    col_id = new_id()
    now = iso_now()
    col_date_str = dt_col.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    due_date_str = dt_due.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    with conn:
        cursor.execute(
            """INSERT INTO collections (id, client_id, assigned_employee_id, total_amount, received_amount, remaining_amount, status, collection_date, due_date, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, 0, ?, 'PENDING', ?, ?, ?, ?, ?)""",
            (
                col_id,
                payload.client,
                payload.assignedEmployee,
                payload.totalAmount,
                payload.totalAmount,
                col_date_str,
                due_date_str,
                payload.notes.strip() if payload.notes else None,
                now,
                now,
            ),
        )

    cursor.execute(f"{REF_JOIN_SELECT} WHERE c.id = ?", (col_id,))
    row = cursor.fetchone()
    return {"collection": map_joined_collection(row)}

@router.get("/{collection_id}")
def get_collection(
    collection_id: str,
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute(f"{REF_JOIN_SELECT} WHERE c.id = ?", (collection_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if current_user["role"] == "EMPLOYEE" and str(row["assigned_employee_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own assigned collections")

    return {"collection": map_joined_collection(row)}

@router.patch("/{collection_id}")
def update_collection(
    collection_id: str,
    payload: UpdateCollectionRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    sets = []
    values = []

    if payload.assignedEmployee is not None:
        cursor.execute("SELECT id, status FROM users WHERE id = ? AND role = 'EMPLOYEE'", (payload.assignedEmployee,))
        emp = cursor.fetchone()
        if not emp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        if emp["status"] != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign to an inactive employee")
        sets.append("assigned_employee_id = ?")
        values.append(emp["id"])

    if payload.totalAmount is not None:
        if payload.totalAmount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Total amount must be greater than 0")
        if payload.totalAmount < existing["received_amount"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Total amount cannot be less than the amount already received",
            )
        rem = payload.totalAmount - existing["received_amount"]
        new_status = compute_status(payload.totalAmount, existing["received_amount"])
        sets.append("total_amount = ?")
        values.append(payload.totalAmount)
        sets.append("remaining_amount = ?")
        values.append(rem)
        sets.append("status = ?")
        values.append(new_status)

    next_col_date = existing["collection_date"]
    next_due_date = existing["due_date"]

    if payload.collectionDate:
        next_col_date = payload.collectionDate
    if payload.dueDate:
        next_due_date = payload.dueDate

    if payload.collectionDate or payload.dueDate:
        try:
            dt_col = datetime.fromisoformat(next_col_date.replace("Z", "+00:00"))
            dt_due = datetime.fromisoformat(next_due_date.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format")

        if dt_due <= dt_col:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Due date must be after the collection date")

        if payload.collectionDate:
            sets.append("collection_date = ?")
            values.append(dt_col.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
        if payload.dueDate:
            sets.append("due_date = ?")
            values.append(dt_due.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")

    if payload.notes is not None:
        sets.append("notes = ?")
        values.append(payload.notes.strip() if payload.notes else None)

    sets.append("updated_at = ?")
    values.append(iso_now())

    values.append(collection_id)
    with conn:
        cursor.execute(f"UPDATE collections SET {', '.join(sets)} WHERE id = ?", values)

    cursor.execute(f"{REF_JOIN_SELECT} WHERE c.id = ?", (collection_id,))
    row = cursor.fetchone()
    return {"collection": map_joined_collection(row)}

@router.delete("/{collection_id}")
def delete_collection(
    collection_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    with conn:
        cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    return {"message": "Collection deleted"}
