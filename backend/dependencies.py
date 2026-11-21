from typing import Any, Callable, Dict, Generator, Optional
import sqlite3
from fastapi import Cookie, Depends, HTTPException, Request, status
from database import get_connection
from crypto_utils import AUTH_COOKIE_NAME, verify_token
from models import ClientDTO, CollectionDTO, PaymentDTO, UserDTO

def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def to_user_dto(row: sqlite3.Row) -> UserDTO:
    return UserDTO(
        id=row["id"],
        name=row["name"],
        username=row["username"],
        phone=row["phone"],
        role=row["role"],
        status=row["status"],
        createdAt=row["created_at"],
    )

def to_client_dto(row: Optional[sqlite3.Row]) -> ClientDTO:
    if not row:
        return ClientDTO(
            id="",
            name="Deleted client",
            phone="",
            address="",
            notes=None,
            createdAt="",
        )
    return ClientDTO(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        address=row["address"],
        notes=row["notes"] if "notes" in row.keys() else None,
        createdAt=row["created_at"],
    )

def to_collection_dto(
    col_row: sqlite3.Row,
    client_row: Optional[sqlite3.Row] = None,
    employee_row: Optional[sqlite3.Row] = None,
) -> CollectionDTO:
    client_dto = to_client_dto(client_row)
    if not employee_row:
        employee_dto = UserDTO(
            id="",
            name="Deleted employee",
            username="",
            phone="",
            role="EMPLOYEE",
            status="INACTIVE",
            createdAt=col_row["created_at"],
        )
    else:
        employee_dto = to_user_dto(employee_row)

    return CollectionDTO(
        id=col_row["id"],
        client=client_dto,
        assignedEmployee=employee_dto,
        totalAmount=float(col_row["total_amount"]),
        receivedAmount=float(col_row["received_amount"]),
        remainingAmount=float(col_row["remaining_amount"]),
        status=col_row["status"],
        collectionDate=col_row["collection_date"],
        dueDate=col_row["due_date"],
        notes=col_row["notes"],
        createdAt=col_row["created_at"],
        updatedAt=col_row["updated_at"],
    )

def to_payment_dto(
    pay_row: sqlite3.Row,
    client_row: Optional[sqlite3.Row] = None,
    employee_row: Optional[sqlite3.Row] = None,
) -> PaymentDTO:
    if client_row:
        client_dto = to_client_dto(client_row)
    else:
        client_dto = ClientDTO(
            id="",
            name=pay_row["client_name"],
            phone=pay_row["client_phone"],
            address="",
            createdAt=pay_row["created_at"],
        )

    if employee_row:
        employee_dto = to_user_dto(employee_row)
    else:
        employee_dto = UserDTO(
            id="",
            name=pay_row["employee_name"],
            username="",
            phone="",
            role="EMPLOYEE",
            status="INACTIVE",
            createdAt=pay_row["created_at"],
        )

    return PaymentDTO(
        id=pay_row["id"],
        collection=pay_row["collection_id"] or "",
        client=client_dto,
        employee=employee_dto,
        amount=float(pay_row["amount"]),
        paymentMethod=pay_row["payment_method"],
        remarks=pay_row["remarks"],
        paymentDate=pay_row["payment_date"],
        createdAt=pay_row["created_at"],
        verified=bool(pay_row["verified"]),
    )

def get_current_user(
    request: Request,
    token: Optional[str] = Cookie(None, alias=AUTH_COOKIE_NAME),
    conn: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    # Also support Authorization: Bearer <token> header for convenience or testing
    auth_header = request.headers.get("Authorization")
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = verify_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user_id = payload.get("sub")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user or user["status"] != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or inactive")

    return user

def require_role(*roles: str) -> Callable:
    def role_checker(current_user: sqlite3.Row = Depends(get_current_user)) -> sqlite3.Row:
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user
    return role_checker
