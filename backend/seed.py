from datetime import datetime, timedelta, timezone
import random
import sqlite3
from database import get_connection, init_db, iso_now, new_id
from crypto_utils import compute_status, encrypt_password, hash_password

PAYMENT_METHODS = ["CASH", "BANK_TRANSFER", "UPI", "OTHER"]

REMARKS_POOL = [
    "Partial payment",
    "Second installment",
    "Full settlement",
    "Cash collected on-site",
    "Cleared outstanding balance",
    "Advance payment",
    "Monthly installment",
]

def seed():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    print("Clearing old data...")
    with conn:
        cursor.execute("DELETE FROM payments")
        cursor.execute("DELETE FROM collections")
        cursor.execute("DELETE FROM clients")
        cursor.execute("DELETE FROM users")

    print("Creating admin dealer...")
    dealer_id = new_id()
    dealer_pw_hash = hash_password("password123")
    dealer_pw_enc = encrypt_password("password123")
    created_at = iso_now()

    with conn:
        cursor.execute(
            """INSERT INTO users (id, name, username, phone, password, encrypted_password, role, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'DEALER', 'ACTIVE', ?)""",
            (dealer_id, "Demo Dealer", "dealer", "9876543210", dealer_pw_hash, dealer_pw_enc, created_at),
        )

    print("Creating employees...")
    employees_data = [
        {"name": "Rahul Sharma", "username": "rahul", "phone": "9876500001"},
        {"name": "Priya Verma", "username": "priya", "phone": "9876500002"},
        {"name": "Arjun Mehta", "username": "arjun", "phone": "9876500003"},
        {"name": "Sneha Iyer", "username": "sneha", "phone": "9876500004"},
    ]
    employees = []
    with conn:
        for emp in employees_data:
            emp_id = new_id()
            pw_hash = hash_password("password123")
            pw_enc = encrypt_password("password123")
            cursor.execute(
                """INSERT INTO users (id, name, username, phone, password, encrypted_password, role, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'EMPLOYEE', 'ACTIVE', ?)""",
                (emp_id, emp["name"], emp["username"], emp["phone"], pw_hash, pw_enc, created_at),
            )
            employees.append({"id": emp_id, "name": emp["name"], "username": emp["username"]})

    print("Creating clients...")
    clients_data = [
        {"name": "Amit Traders", "phone": "9111100001", "address": "MG Road, Pune", "notes": "Wholesale buyer"},
        {"name": "Singh Enterprises", "phone": "9111100002", "address": "Sector 18, Noida"},
        {"name": "Kumar & Sons", "phone": "9111100003", "address": "Anna Nagar, Chennai"},
        {"name": "Sunrise Distributors", "phone": "9111100004", "address": "Salt Lake, Kolkata"},
        {"name": "Green Valley Store", "phone": "9111100005", "address": "Banjara Hills, Hyderabad"},
        {"name": "Metro Wholesale", "phone": "9111100006", "address": "Andheri East, Mumbai"},
        {"name": "Coastal Traders", "phone": "9111100007", "address": "Marine Drive, Kochi"},
        {"name": "Highland Retailers", "phone": "9111100008", "address": "Sector 5, Shimla"},
        {"name": "Delta Distributors", "phone": "9111100009", "address": "Civil Lines, Jaipur"},
        {"name": "Riverside Mart", "phone": "9111100010", "address": "Riverside Road, Ahmedabad"},
        {"name": "Prime Traders", "phone": "9111100011", "address": "Park Street, Kolkata"},
        {"name": "Nova Enterprises", "phone": "9111100012", "address": "HSR Layout, Bengaluru"},
    ]
    clients = []
    with conn:
        for c in clients_data:
            c_id = new_id()
            cursor.execute(
                """INSERT INTO clients (id, name, phone, address, notes, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (c_id, c["name"], c["phone"], c["address"], c.get("notes"), dealer_id, created_at),
            )
            clients.append({"id": c_id, "name": c["name"], "phone": c["phone"]})

    print("Creating collections and payment history...")
    now_dt = datetime.now(timezone.utc)
    seed_start = now_dt - timedelta(days=120)
    rng = random.Random(20260901)

    with conn:
        for _ in range(60):
            client = rng.choice(clients)
            employee = rng.choice(employees)
            total_amount = rng.randint(4, 40) * 5000.0  # 20,000 - 200,000

            col_offset_days = rng.randint(0, 100)
            col_date = seed_start + timedelta(days=col_offset_days)
            col_date = col_date.replace(hour=rng.randint(9, 17), minute=rng.randint(0, 59))
            due_date = col_date + timedelta(days=rng.randint(14, 45))

            roll = rng.random()
            if roll < 0.35:
                target_received = 0.0
            elif roll < 0.70:
                pct = rng.randint(20, 80) / 100.0
                target_received = round((total_amount * pct) / 500.0) * 500.0
            else:
                target_received = total_amount

            num_payments = 0 if target_received == 0 else rng.randint(1, 3)
            payments_plan = []
            remaining_to_allocate = target_received

            for p in range(num_payments):
                is_last = (p == num_payments - 1)
                if is_last:
                    amt = remaining_to_allocate
                else:
                    portion = rng.randint(30, 70) / 100.0
                    amt = round((remaining_to_allocate * portion) / 500.0) * 500.0 or remaining_to_allocate

                if amt <= 0:
                    continue
                remaining_to_allocate -= amt

                latest_possible = min(due_date, now_dt)
                span = max(1, int((latest_possible - col_date).total_seconds() // 86400))
                p_date = col_date + timedelta(days=rng.randint(1, span), hours=rng.randint(1, 8))

                payments_plan.append({
                    "amount": amt,
                    "method": rng.choice(PAYMENT_METHODS),
                    "date": p_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    "remarks": rng.choice(REMARKS_POOL),
                })

            received_amount = sum(p["amount"] for p in payments_plan)
            remaining_amount = total_amount - received_amount
            col_status = compute_status(total_amount, received_amount)
            col_id = new_id()
            c_now = iso_now()

            cursor.execute(
                """INSERT INTO collections (id, client_id, assigned_employee_id, total_amount, received_amount, remaining_amount, status, collection_date, due_date, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    col_id,
                    client["id"],
                    employee["id"],
                    total_amount,
                    received_amount,
                    remaining_amount,
                    col_status,
                    col_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    due_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    "",
                    c_now,
                    c_now,
                ),
            )

            for p in payments_plan:
                p_id = new_id()
                cursor.execute(
                    """INSERT INTO payments (id, collection_id, client_id, employee_id, client_name, client_phone, employee_name, amount, payment_method, remarks, payment_date, created_at, verified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (
                        p_id,
                        col_id,
                        client["id"],
                        employee["id"],
                        client["name"],
                        client["phone"],
                        employee["name"],
                        p["amount"],
                        p["method"],
                        p["remarks"],
                        p["date"],
                        c_now,
                    ),
                )

    conn.close()
    print("Database seeding completed successfully!")
    print("\nDemo Credentials:")
    print("  Dealer:   dealer / password123")
    for emp in employees_data:
        print(f"  Employee: {emp['username']} / password123")

if __name__ == "__main__":
    seed()
