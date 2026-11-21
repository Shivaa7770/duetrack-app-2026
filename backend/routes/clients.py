import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from database import iso_now, new_id
from dependencies import (
    get_current_user,
    get_db,
    require_role,
    to_client_dto,
    to_collection_dto,
)
from models import ClientDTO, CreateClientRequest, UpdateClientRequest

router = APIRouter(prefix="/api/clients", tags=["clients"])

@router.get("")
def list_clients(
    search: Optional[str] = Query(None),
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    if search and search.strip():
        like = f"%{search.strip()}%"
        cursor.execute(
            "SELECT * FROM clients WHERE name LIKE ? OR phone LIKE ? ORDER BY created_at DESC",
            (like, like),
        )
    else:
        cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")

    rows = cursor.fetchall()
    return {"clients": [to_client_dto(r) for r in rows]}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(
    payload: CreateClientRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    client_id = new_id()
    created_at = iso_now()
    cursor = conn.cursor()

    with conn:
        cursor.execute(
            """INSERT INTO clients (id, name, phone, address, notes, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                payload.name.strip(),
                payload.phone.strip(),
                payload.address.strip(),
                payload.notes.strip() if payload.notes else None,
                current_user["id"],
                created_at,
            ),
        )

    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    row = cursor.fetchone()
    return {"client": to_client_dto(row)}

@router.get("/{client_id}")
def get_client(
    client_id: str,
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    client_row = cursor.fetchone()
    if not client_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # Fetch all collections for this client with assigned employee info
    cursor.execute(
        """SELECT c.*, u.id AS u_id, u.name AS u_name, u.username AS u_username,
                  u.phone AS u_phone, u.role AS u_role, u.status AS u_status, u.created_at AS u_created_at
           FROM collections c
           LEFT JOIN users u ON u.id = c.assigned_employee_id
           WHERE c.client_id = ?
           ORDER BY c.created_at DESC""",
        (client_id,),
    )
    col_rows = cursor.fetchall()

    total_amount = 0.0
    received_amount = 0.0
    remaining_amount = 0.0
    collections = []

    for r in col_rows:
        total_amount += float(r["total_amount"])
        received_amount += float(r["received_amount"])
        remaining_amount += float(r["remaining_amount"])

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
        collections.append(to_collection_dto(r, client_row, emp_row))

    client_dto = to_client_dto(client_row).model_dump(by_alias=True)
    client_dto.update({
        "totalAmount": total_amount,
        "receivedAmount": received_amount,
        "remainingAmount": remaining_amount,
    })

    return {
        "client": client_dto,
        "collections": collections,
    }

@router.patch("/{client_id}")
def update_client(
    client_id: str,
    payload: UpdateClientRequest,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    sets = []
    values = []

    if payload.name is not None:
        sets.append("name = ?")
        values.append(payload.name.strip())
    if payload.phone is not None:
        sets.append("phone = ?")
        values.append(payload.phone.strip())
    if payload.address is not None:
        sets.append("address = ?")
        values.append(payload.address.strip())
    if payload.notes is not None:
        sets.append("notes = ?")
        values.append(payload.notes.strip() if payload.notes else None)

    if sets:
        values.append(client_id)
        with conn:
            cursor.execute(f"UPDATE clients SET {', '.join(sets)} WHERE id = ?", values)

    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    updated = cursor.fetchone()
    return {"client": to_client_dto(updated)}

@router.delete("/{client_id}")
def delete_client(
    client_id: str,
    current_user: sqlite3.Row = Depends(require_role("DEALER")),
    conn: sqlite3.Connection = Depends(get_db),
):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS count FROM collections WHERE client_id = ? AND status != 'COMPLETED'",
        (client_id,),
    )
    active_count = cursor.fetchone()["count"]
    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a client with pending or partially collected collections",
        )

    with conn:
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    return {"message": "Client deleted"}
