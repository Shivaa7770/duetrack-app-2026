from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query
from dependencies import get_current_user, get_db
from models import EmployeeBreakdownItem, PeriodReportDTO, StatusBreakdown
from routes.dashboard import VALID_PERIODS, get_start_date_for_period

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/daily")
def get_daily_report(
    period: str = Query("week"),
    current_user: sqlite3.Row = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    if period not in VALID_PERIODS:
        period = "week"

    start_date = get_start_date_for_period(period)

    pay_clauses = []
    pay_values = []
    if current_user["role"] == "EMPLOYEE":
        pay_clauses.append("employee_id = ?")
        pay_values.append(current_user["id"])
    if start_date:
        pay_clauses.append("payment_date >= ?")
        pay_values.append(start_date)

    pay_where = f"WHERE {' AND '.join(pay_clauses)}" if pay_clauses else ""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT employee_id, employee_name, amount FROM payments {pay_where} ORDER BY created_at DESC",
        pay_values,
    )
    payments = cursor.fetchall()

    total_collected = 0.0
    employee_map: Dict[str, Dict[str, Any]] = {}

    for p in payments:
        amount = float(p["amount"])
        total_collected += amount
        emp_id = p["employee_id"] or ""
        if emp_id not in employee_map:
            employee_map[emp_id] = {
                "employeeId": emp_id,
                "employeeName": p["employee_name"],
                "totalCollected": 0.0,
                "paymentCount": 0,
            }
        employee_map[emp_id]["totalCollected"] += amount
        employee_map[emp_id]["paymentCount"] += 1

    employee_breakdown = sorted(
        employee_map.values(),
        key=lambda x: x["totalCollected"],
        reverse=True,
    )

    col_clauses = []
    col_values = []
    if current_user["role"] == "EMPLOYEE":
        col_clauses.append("assigned_employee_id = ?")
        col_values.append(current_user["id"])

    col_where = f"WHERE {' AND '.join(col_clauses)}" if col_clauses else ""
    cursor.execute(f"SELECT status FROM collections {col_where}", col_values)
    cols = cursor.fetchall()

    pending_count = 0
    partially_collected_count = 0
    completed_count = 0

    for c in cols:
        if c["status"] == "PENDING":
            pending_count += 1
        elif c["status"] == "PARTIALLY_COLLECTED":
            partially_collected_count += 1
        else:
            completed_count += 1

    return {
        "period": period,
        "totalCollected": total_collected,
        "paymentCount": len(payments),
        "employeeBreakdown": employee_breakdown,
        "statusBreakdown": {
            "pending": pending_count,
            "partiallyCollected": partially_collected_count,
            "completed": completed_count,
        },
    }
