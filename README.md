# Eco Kaitiaki Hub 🌿

**A web platform for ecological conservation teams to manage field operations, track pest control data, and monitor environmental impact.**

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.1-lightgrey.svg)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/mysql-8.0-blue.svg)]
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📖 About

Eco Kaitiaki Hub is a full-stack conservation management platform originally developed as part of Lincoln University's COMP639 Studio Project and further refined, deployed, and maintained as a personal portfolio project. The app helps conservation groups coordinate their field work — tracking where traps and bait stations are deployed, recording pest catches, managing equipment inventory, and visualising trends through dashboards.

It's designed around a **multi-group model**: each conservation group operates independently, with its own members, trap lines, storage areas, and data. Role-based access ensures field operators only see what they need, while coordinators and admins get a broader view.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13, Flask 3.1 |
| **Database** | MySQL 8.0, PyMySQL |
| **Frontend** | Jinja2 templates, Bootstrap 5, Vanilla JS, jQuery DataTables |
| **Auth** | Flask-BCrypt (password hashing), custom RBAC decorators |
| **PDF Export** | `fpdf2` |
| **Testing** | `pytest` (60+ tests), `flake8` |
| **CI** | GitHub Actions automated testing workflow |

No heavy ORMs or frontend frameworks — deliberately kept lean to focus on understanding how the web stack fits together end-to-end.

---

## ✨ Features

- **Role-Based Access Control** — Four roles (Super Admin, Group Coordinator, Operator, Observer) with row-level data isolation per conservation group
- **Trap & Bait Station Management** — Create, deploy, and track equipment along geographic trap lines
- **Catch Recording** — Log pest catches with species, trap location, and timestamps; supports historical record browsing
- **Inventory System** — Track equipment across storage areas; stock-level alerts and audit logs
- **Analytics Dashboard** — Charts and metrics for catch trends, species distribution, and group-level comparisons
- **PDF Export** — Generate downloadable reports from analytics data
- **Knowledge Hub** — Community-contributed articles and resources for conservation best practices
- **Group Updates** — Coordinators can post updates with photos to their group members
- **Global Equipment Map** — Visual overview of all trap lines and their boundaries across groups
- **AJAX Status Updates** — Inline equipment status changes without page reloads

---

## 👩‍💻 My Role

As part of a five-person development team, I contributed to backend development, database-driven features, analytics, and deployment.

- **Trend Analytics** — Built the trend analytics dashboard that visualises catch data over time, helping groups spot patterns in pest activity
- **PDF Report Export** — Implemented server-side PDF generation so coordinators can download and share field reports
- **Analytics Dashboard** — Designed and built the analytics views (charts, aggregated stats) consumed by admins and observers
- **Historical Records** — Added the ability to browse and review past catch and bait station records
- **Knowledge Hub** — Contributed to the community knowledge-sharing feature, including submission and review flows
- **Group Updates** — Built the photo update system for group coordinators to communicate with their field teams
- **UI Polish** — Navigation bar fixes, layout improvements, and general frontend cleanup across multiple templates

I also participated in code review, merge conflict resolution, and manual testing across feature branches.

---

## 📸 Screenshots


### Dashboard

![Dashboard](screenshots/dashboard.png)


### Trap Management

![Line Management](screenshots/lines.png)


### Analytics Dashboard

![Analytics](screenshots/analytics.png)


### Knowledge Hub

![Knowledge Hub](screenshots/knowledge.png)

---

## 🚀 Live Demo

The application is deployed on PythonAnywhere:

🌐 https://qichang1128954.pythonanywhere.com

Demo accounts are available for testing:
| Username | Password | Role |
|---|---|---|
| `superadmin` | `Password123!` | Super Admin |
| `coord_Alice` | `Password123!` | Group Coordinator |
| `coord_charlie` | `Password123!` | Group Coordinator |
| `op_dave` | `Password123!` | Operator |

---

## 💻 Running Locally

### Prerequisites
- Python 3.13+
- PostgreSQL 15+

### Setup

```bash
# Clone the repo
git clone https://github.com/Charmaine-Chang/eco_kaitiaki_hub.git
cd PF_LU

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Database

Create a local PostgreSQL database, then configure your connection in `PF_LU_APP/connect_local.py`:

```python
dbuser = "your_username"
dbpass = "your_password"
dbhost = "localhost"
dbport = "5432"
dbname = "your_db_name"
```

Load the schema and seed data:

```bash
myql -h localhost -U your_username -d your_db_name -f sql/create_database.sql
myql -h localhost -U your_username -d your_db_name -f sql/populate_database.sql
```

### Run

```bash
python -m PF_LU_APP.run
```

Open `http://127.0.0.1:5000`. Test accounts are available in the seed data — log in as `superadmin`, `coord_Alice`, `coord_charlie`, or `op_dave` (all use password `Password123!`).

### Tests

```bash
pytest -v
```

---

## 📚 What I Learned

- **Working in a team of five** with git branching, pull requests, and merge conflict resolution on a real codebase
- **Designing database-backed features** from scratch — thinking through schema changes, query patterns, and how the data flows to the frontend
- **Building analytics views** with aggregated SQL queries and presenting the results clearly in charts and tables
- **Server-side PDF generation** — generating structured documents from database data using `fpdf2`
- **Flask patterns** — Blueprints, route decorators, Jinja2 templating, and custom RBAC middleware
- **The value of writing tests** — our test suite caught regressions multiple times during feature integration
- **Reading and contributing to a codebase someone else started** — most of the app skeleton existed before I joined; I learned to navigate unfamiliar code, follow existing patterns, and extend them without breaking things

---

## 🔮 Future Improvements

If I were to continue this project, here's what I'd focus on:

- **Replace jQuery DataTables** with a lighter approach (htmx or a small vanilla JS library) — DataTables works but feels heavy for what we use it for
- **Add a REST API layer** — currently everything is server-rendered; an API would make it easier to build a mobile-friendly frontend later
- **Improve test coverage in analytics** — the analytics queries are the most complex part of the app and deserve more thorough testing
- **Mobile-responsive field views** — operators in the field need a better mobile experience for recording catches
- **Docker Compose setup** — one-command startup would lower the barrier for new contributors and reviewers

---

## 👥 Team

Developed at Lincoln University (COMP639, Semester 1 2026) by **Team Mokomoko**:

- Michael Zheng
- Charles Ma
- Kristen Dai
- Yue Qian
- **Qi Chang** — [github.com/Charmaine-Chang](https://github.com/Charmaine-Chang)

---

## 🌐 Deployment

The application is deployed using:

- PythonAnywhere
- MySQL database
- Flask WSGI application server

Deployment process includes:
- Virtual environment configuration
- Environment-specific database settings
- WSGI configuration
- Production database migration

---

*Built as part of the Predator Free Lincoln University initiative. MIT License.*
