# DueTrack - Payment Collection Management System

A production-ready payment collection tracker for field operations: dealers assign collections to employees, employees record payments as they collect them in the field, and the dealer dashboard reflects updated balances automatically in real time.

---

## 🛠️ Tech Stack

### Frontend
- **Framework:** [React 18](https://react.dev/) + [Vite](https://vitejs.dev/) + [TypeScript](https://www.typescriptlang.org/)
- **Styling & UI:** [Tailwind CSS](https://tailwindcss.com/) (`tailwind.config.ts` configures design tokens, theme colors, and animations), [shadcn/ui](https://ui.shadcn.com/), [Radix UI](https://www.radix-ui.com/), [Lucide React](https://lucide.dev/) icons
- **State & Data Fetching:** [TanStack Query (React Query)](https://tanstack.com/query/latest), [Axios](https://axios-http.com/)
- **Routing:** [React Router v6](https://reactrouter.com/)

### Backend
- **Language & Framework:** [Python 3](https://www.python.org/) + [FastAPI](https://fastapi.tiangolo.com/) (high-performance asynchronous REST API)
- **Interactive Documentation:** Automatic OpenAPI Swagger UI at `http://localhost:8000/docs` and ReDoc at `http://localhost:8000/redoc`
- **Data Validation & Schemas:** [Pydantic v2](https://docs.pydantic.dev/)
- **Database:** SQLite (`duetrack.db`) with foreign key constraints, indexes, and atomic transactions
- **Authentication & Security:**
  - JWT tokens stored in `httpOnly`, `SameSite=Lax` cookies (`token`)
  - Irreversible password hashing with `bcrypt`
  - AES-256-GCM symmetric encryption for dealer-reversible employee password management
  - Role-Based Access Control (`DEALER` and `EMPLOYEE` guards)


## 📂 Project Structure

```
DueTrack-main/
├── backend/                   # Python FastAPI Backend
│   ├── .venv/                 # Python virtual environment
│   ├── migrations/            # Raw SQL migration files (0001_init.sql, 0002_...)
│   ├── routes/                # REST API endpoints
│   │   ├── auth.py            # Login, logout, /me, password reveal & change, dealer CRUD
│   │   ├── clients.py         # Client CRUD, search, collection history & balance totals
│   │   ├── employees.py       # Employee CRUD, performance metrics, password inspection
│   │   ├── collections.py     # Assignment, status computation, filters
│   │   ├── payments.py        # Field payment recording, balance updates & rollback, verification
│   │   ├── dashboard.py       # Period metrics (today/week/month/year/all)
│   │   └── reports.py         # Daily & periodic collection report by employee and status
│   ├── main.py                # FastAPI app, CORS middleware, error handlers
│   ├── database.py            # SQLite connection pool & auto-table initializer
│   ├── crypto_utils.py        # bcrypt, AES-256-GCM, and JWT signing/verification
│   ├── models.py              # Pydantic v2 request & response models
│   ├── dependencies.py        # Auth session extraction & RBAC role guards
│   ├── seed.py                # Database seeder with demo accounts, clients, collections & payments
│   ├── test_api.py            # Automated end-to-end backend test suite
│   ├── requirements.txt       # Python package dependencies
│   ├── duetrack.db            # Seeded SQLite database file
│   ├── .env                   # Backend environment configuration
│   └── .env.example           # Example backend configuration
├── client/                    # React + Vite Frontend
│   ├── src/                   # React source code
│   │   ├── components/        # UI components, layout, dialogs, tables, cards
│   │   ├── pages/             # Dealer & Employee dashboards, clients, collections, history
│   │   ├── services/          # Axios API client & error handling
│   │   ├── hooks/             # Authentication & React Query hooks
│   │   └── lib/               # Utility functions
│   ├── tailwind.config.ts     # Tailwind CSS theme configuration (REQUIRED)
│   ├── vite.config.ts         # Vite configuration with /api proxy to http://localhost:8000
│   ├── tsconfig.json          # TypeScript project configuration
│   └── .env.example           # Example client configuration
├── shared/                    # Shared TypeScript domain types
│   ├── types/index.ts         # Shared interfaces (UserDTO, CollectionDTO, etc.)
│   └── package.json
├── package.json               # Root scripts orchestrating backend & frontend
├── .env.example               # Root unified environment example
├── .gitignore                 # Configured for Node, Python, SQLite & OS files
└── README.md                  # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** (Python 3.14 verified)
- **Node.js 18.18+** & npm

### 2. Quick Setup (Automated)

Run the single setup command from the project root:
```bash
npm run setup
```
This command:
1. Installs all frontend npm dependencies.
2. Creates the Python virtual environment in `backend/.venv`.
3. Installs all Python dependencies from `backend/requirements.txt`.
4. Seeds the database with demo accounts, clients, and collection history.

*(Or setup manually:)*
```bash
# 1. Install frontend dependencies
npm install

# 2. Setup Python backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Seed demo data
python seed.py
cd ..
```

---

## 🏃 Running the Application

### Option 1: Run Both Together (Recommended)
From the project root:
```bash
npm run dev
```
This concurrently launches:
- **Backend (Python FastAPI):** `http://localhost:8000`
- **Frontend (React + Vite):** `http://localhost:5173`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`

### Option 2: Run Separately in Two Terminals

**Terminal 1 — Backend:**
```bash
npm run dev:backend
# or: cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
npm run dev:client
# or: cd client && npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 🔑 Demo Credentials

The database is pre-seeded with sample data:

| Role | Username | Password | Notes |
|---|---|---|---|
| **Dealer (Admin)** | `dealer` | `password123` | Full dashboard access, manage employees, clients, collections & passwords |
| **Employee** | `rahul` | `password123` | Field agent view, assigned collections, submit payments |
| **Employee** | `priya` | `password123` | Field agent view, assigned collections, submit payments |
| **Employee** | `arjun` | `password123` | Field agent view, assigned collections, submit payments |
| **Employee** | `sneha` | `password123` | Field agent view, assigned collections, submit payments |

> To reset and re-seed the demo database at any time, run:
> ```bash
> npm run seed
> ```

---

## 🧪 Testing & Type Checking

Run all test suites across the project:
```bash
npm test
```
This automatically executes:
1. **Python API Tests:** `backend/test_api.py` via `npm run test:backend` (verifies authentication, AES-256-GCM encryption, CRUD, balance calculations, rollback logic).
2. **TypeScript Typecheck:** `client` via `npm run typecheck` (`tsc -b --noEmit`).

---

## 📡 REST API Reference

All endpoints are prefixed with `/api` and return JSON.

### Authentication (`/api/auth`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/api/auth/login` | Authenticate and set `token` httpOnly cookie | Public |
| `POST` | `/api/auth/logout` | Clear `token` cookie | Public |
| `GET` | `/api/auth/me` | Get current logged-in user profile | Authenticated |
| `PATCH` | `/api/auth/me` | Update name and username | Authenticated |
| `GET` | `/api/auth/me/password` | View decrypted password | Dealer |
| `PATCH` | `/api/auth/me/password` | Change user password | Authenticated |
| `GET` | `/api/auth/dealers` | List dealer accounts | Dealer |
| `POST` | `/api/auth/dealers` | Create new dealer account | Main Dealer |
| `DELETE` | `/api/auth/dealers/{id}` | Delete dealer account | Main Dealer |

### Clients (`/api/clients`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/clients` | List clients (optional `?search=...`) | Authenticated |
| `POST` | `/api/clients` | Create new client | Dealer |
| `GET` | `/api/clients/{id}` | Client detail + total/received/remaining balances | Authenticated |
| `PATCH` | `/api/clients/{id}` | Update client details | Dealer |
| `DELETE` | `/api/clients/{id}` | Delete client (checks for active collections) | Dealer |

### Employees (`/api/employees`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/employees` | List employee accounts | Dealer |
| `POST` | `/api/employees` | Create new employee account | Dealer |
| `GET` | `/api/employees/{id}` | Employee detail + performance statistics | Dealer |
| `GET` | `/api/employees/{id}/password` | Reveal employee password | Dealer |
| `PATCH` | `/api/employees/{id}` | Update employee profile or password | Dealer |
| `DELETE` | `/api/employees/{id}` | Delete employee (checks for active collections) | Dealer |

### Collections (`/api/collections`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/collections` | List collections (filters: status, employee, client, dates) | Authenticated |
| `POST` | `/api/collections` | Assign new collection to employee | Dealer |
| `GET` | `/api/collections/{id}` | View collection details | Authenticated |
| `PATCH` | `/api/collections/{id}` | Update amount, dates, or reassign employee | Dealer |
| `DELETE` | `/api/collections/{id}` | Delete collection | Dealer |

### Payments (`/api/payments`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/payments` | List payments (optional `?collection=...`) | Authenticated |
| `POST` | `/api/payments` | Record payment in field (atomic balance update) | Employee |
| `GET` | `/api/payments/{id}` | View payment details | Authenticated |
| `PATCH` | `/api/payments/{id}` | Edit payment amount (recalculates balances) | Dealer |
| `PATCH` | `/api/payments/{id}/verify` | Mark payment as verified | Dealer |
| `DELETE` | `/api/payments/{id}` | Delete payment (reverts collection balances) | Dealer |

### Dashboard & Reports
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/dashboard` | Dashboard cards (`?period=today\|week\|month\|year\|all`) | Authenticated |
| `GET` | `/api/reports/daily` | Periodic report with employee & status breakdown | Authenticated |
| `GET` | `/api/health` | Service health status check | Public |
