from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, Query
from dependencies import get_current_user, get_db
from models import DashboardSummaryDTO
from routes.collections import REF_JOIN_SELECT, map_joined_collection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

VALID_PERIODS = ["today", "week", "month", "year", "all"]

def get_start_date_for_period(period: str) -> Optional[str]:
    if period == "all":
        return None
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    days = 7 if period == "week" else (30 if period == "month" else 365)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

@router.get("")
def get_dashboard(
    period: str = Query("week"),
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if period not in VALID_PERIODS:
        period = "week"

    start_date = get_start_date_for_period(period)

    # Filter collections
    col_clauses = []
    col_values = []
    if current_user["role"] == "EMPLOYEE":
        col_clauses.append("assigned_employee_id = ?")
        col_values.append(current_user["id"])
    if start_date:
        col_clauses.append("collection_date >= ?")
        col_values.append(start_date)

    col_where = f"WHERE {' AND '.join(col_clauses)}" if col_clauses else ""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM collections {col_where}", col_values)
    cols = cursor.fetchall()

    total_amount = 0.0
    total_remaining = 0.0
    pending_count = 0
    partially_collected_count = 0
    completed_count = 0

    for c in cols:
        total_amount += float(c["total_amount"])
        total_remaining += float(c["remaining_amount"])
        if c["status"] == "PENDING":
            pending_count += 1
        elif c["status"] == "PARTIALLY_COLLECTED":
            partially_collected_count += 1
        else:
            completed_count += 1

    # Filter payments for totalReceived during period
    pay_clauses = []
    pay_values = []
    if current_user["role"] == "EMPLOYEE":
        pay_clauses.append("employee_id = ?")
        pay_values.append(current_user["id"])
    if start_date:
        pay_clauses.append("payment_date >= ?")
        pay_values.append(start_date)

    pay_where = f"WHERE {' AND '.join(pay_clauses)}" if pay_clauses else ""
    cursor.execute(f"SELECT amount FROM payments {pay_where}", pay_values)
    pay_rows = cursor.fetchall()
    total_received = sum(float(r["amount"]) for r in pay_rows)

    # 7 recent collections
    recent_col_clauses = []
    recent_col_values = []
    if current_user["role"] == "EMPLOYEE":
        recent_col_clauses.append("c.assigned_employee_id = ?")
        recent_col_values.append(current_user["id"])
    if start_date:
        recent_col_clauses.append("c.collection_date >= ?")
        recent_col_values.append(start_date)

    recent_col_where = f"WHERE {' AND '.join(recent_col_clauses)}" if recent_col_clauses else ""
    recent_query = f"{REF_JOIN_SELECT} {recent_col_where} ORDER BY c.updated_at DESC LIMIT 7"
    cursor.execute(recent_query, recent_col_values)
    recent_rows = cursor.fetchall()
    recent_collections = [map_joined_collection(r) for r in recent_rows]

    return {
        "totalAmount": total_amount,
        "totalReceived": total_received,
        "totalRemaining": total_remaining,
        "pendingCount": pending_count,
        "partiallyCollectedCount": partially_collected_count,
        "completedCount": completed_count,
        "recentCollections": recent_collections,
    }
