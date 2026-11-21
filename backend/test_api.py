"""
Comprehensive automated test suite for DueTrack FastAPI backend.
Run with: python test_api.py or pytest
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    print("✓ Health check passed")

def test_auth_and_dealer_flow():
    # 1. Invalid login
    bad_res = client.post("/api/auth/login", json={"username": "dealer", "password": "wrongpassword"})
    assert bad_res.status_code == 401
    assert "Invalid username or password" in bad_res.json().get("message", "")

    # 2. Valid dealer login
    res = client.post("/api/auth/login", json={"username": "dealer", "password": "password123"})
    assert res.status_code == 200
    user = res.json().get("user")
    assert user["role"] == "DEALER"
    assert user["username"] == "dealer"
    assert "token" in client.cookies

    # 3. Check /me
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["id"] == user["id"]

    # 4. Dealer password view (reversible AES-256-GCM)
    pw_res = client.get("/api/auth/me/password")
    assert pw_res.status_code == 200
    assert pw_res.json()["password"] == "password123"

    # 5. List dealers
    dealers_res = client.get("/api/auth/dealers")
    assert dealers_res.status_code == 200
    assert len(dealers_res.json()["dealers"]) >= 1
    assert dealers_res.json()["isMainDealer"] is True

    print("✓ Auth & dealer flow passed")

def test_clients_crud():
    # Login as dealer
    client.post("/api/auth/login", json={"username": "dealer", "password": "password123"})

    # 1. List clients
    list_res = client.get("/api/clients")
    assert list_res.status_code == 200
    initial_count = len(list_res.json()["clients"])

    # 2. Create client
    create_res = client.post("/api/clients", json={
        "name": "Acme Industrial Co",
        "phone": "9998887770",
        "address": "42 Tech Park, Bangalore",
        "notes": "Premium enterprise account"
    })
    assert create_res.status_code == 201
    new_client = create_res.json()["client"]
    client_id = new_client["id"]
    assert new_client["name"] == "Acme Industrial Co"

    # 3. Get client detail
    detail_res = client.get(f"/api/clients/{client_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["client"]["id"] == client_id

    # 4. Update client
    update_res = client.patch(f"/api/clients/{client_id}", json={
        "notes": "Updated notes"
    })
    assert update_res.status_code == 200
    assert update_res.json()["client"]["notes"] == "Updated notes"

    # 5. Delete client
    del_res = client.delete(f"/api/clients/{client_id}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Client deleted"

    print("✓ Clients CRUD passed")

def test_employees_flow():
    # Login as dealer
    client.post("/api/auth/login", json={"username": "dealer", "password": "password123"})

    # 1. List employees
    emp_res = client.get("/api/employees")
    assert emp_res.status_code == 200
    employees = emp_res.json()["employees"]
    assert len(employees) >= 1
    first_emp = employees[0]

    # 2. Get employee detail with performance
    detail_res = client.get(f"/api/employees/{first_emp['id']}")
    assert detail_res.status_code == 200
    assert "performance" in detail_res.json()

    # 3. View employee password
    pw_res = client.get(f"/api/employees/{first_emp['id']}/password")
    assert pw_res.status_code == 200
    assert pw_res.json()["password"] == "password123"

    print("✓ Employees flow passed")

def test_collections_and_payments_workflow():
    # Login as dealer to find an employee and client
    client.post("/api/auth/login", json={"username": "dealer", "password": "password123"})
    clients = client.get("/api/clients").json()["clients"]
    employees = client.get("/api/employees").json()["employees"]
    test_client = clients[0]
    test_emp = [e for e in employees if e["username"] == "rahul"][0]

    # 1. Dealer creates collection
    col_create_res = client.post("/api/collections", json={
        "client": test_client["id"],
        "assignedEmployee": test_emp["id"],
        "totalAmount": 50000,
        "collectionDate": "2026-11-20T00:00:00.000Z",
        "dueDate": "2026-12-20T00:00:00.000Z",
        "notes": "Quarterly invoice collection"
    })
    assert col_create_res.status_code == 201
    col = col_create_res.json()["collection"]
    col_id = col["id"]
    assert col["totalAmount"] == 50000
    assert col["remainingAmount"] == 50000
    assert col["status"] == "PENDING"

    # 2. Login as Employee (Rahul)
    emp_client = TestClient(app)
    emp_login = emp_client.post("/api/auth/login", json={"username": "rahul", "password": "password123"})
    assert emp_login.status_code == 200

    # 3. Employee adds a payment
    pay_res = emp_client.post("/api/payments", json={
        "collection": col_id,
        "amount": 20000,
        "paymentMethod": "UPI",
        "paymentDate": "2026-11-21",
        "remarks": "First installment received via UPI"
    })
    assert pay_res.status_code == 201
    payment = pay_res.json()["payment"]
    payment_id = payment["id"]
    assert payment["amount"] == 20000

    # 4. Verify collection updated atomically
    col_check = emp_client.get(f"/api/collections/{col_id}")
    assert col_check.status_code == 200
    updated_col = col_check.json()["collection"]
    assert updated_col["receivedAmount"] == 20000
    assert updated_col["remainingAmount"] == 30000
    assert updated_col["status"] == "PARTIALLY_COLLECTED"

    # 5. Dealer verifies payment
    verify_res = client.patch(f"/api/payments/{payment_id}/verify", json={"verified": True})
    assert verify_res.status_code == 200
    assert verify_res.json()["payment"]["verified"] is True

    # 6. Dealer updates payment amount to 25000
    update_pay_res = client.patch(f"/api/payments/{payment_id}", json={
        "amount": 25000,
        "remarks": "Corrected UPI settlement amount"
    })
    assert update_pay_res.status_code == 200
    col_check2 = client.get(f"/api/collections/{col_id}")
    assert col_check2.json()["collection"]["remainingAmount"] == 25000

    # 7. Dealer deletes payment -> rolls back collection balance
    del_pay_res = client.delete(f"/api/payments/{payment_id}")
    assert del_pay_res.status_code == 200
    col_check3 = client.get(f"/api/collections/{col_id}")
    assert col_check3.json()["collection"]["remainingAmount"] == 50000
    assert col_check3.json()["collection"]["status"] == "PENDING"

    # 8. Clean up test collection
    client.delete(f"/api/collections/{col_id}")

    print("✓ Collections & payments atomic workflow passed")

def test_dashboard_and_reports():
    client.post("/api/auth/login", json={"username": "dealer", "password": "password123"})

    # Dashboard
    dash_res = client.get("/api/dashboard?period=all")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "totalAmount" in dash_data
    assert "totalReceived" in dash_data
    assert "totalRemaining" in dash_data
    assert "recentCollections" in dash_data

    # Daily report
    report_res = client.get("/api/reports/daily?period=month")
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert "totalCollected" in report_data
    assert "employeeBreakdown" in report_data
    assert "statusBreakdown" in report_data

    print("✓ Dashboard & reports passed")

if __name__ == "__main__":
    print("\nRunning DueTrack API Tests...")
    test_health()
    test_auth_and_dealer_flow()
    test_clients_crud()
    test_employees_flow()
    test_collections_and_payments_workflow()
    test_dashboard_and_reports()
    print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!\n")
