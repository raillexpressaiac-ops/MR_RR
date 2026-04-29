# SRPS Cargo — Flask + PostgreSQL

Unified Flask app for both the **MR Management System** and the **RR Manager (Hamali Calculator)**. Same UI/logic as the original HTML files — only the storage layer is now PostgreSQL instead of localStorage.

## Setup

1. Make sure PostgreSQL is running locally (creds already in `.env`).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app.py
   ```
   On first run it will auto-create the `srps_cargo` database, all 4 tables, and seed default trains (9 MR trains + 8 RR trains).

## Usage

- MR Management System → http://localhost:5000/mr
- RR Manager → http://localhost:5000/rr
- Header has a switcher pill to jump between the two.

## Project layout

```
srps_flask/
├── app.py                  # Flask app + REST APIs
├── schema.sql              # Tables + seed data
├── requirements.txt
├── .env                    # DB credentials
└── templates/
    ├── mr_system.html      # MR UI (unchanged design)
    └── rr_manager.html     # RR UI (unchanged design)
```

## Database tables

- `mr_trains`, `mr_entries` — MR system (online/offline modes)
- `rr_trains`, `rr_entries` — RR system (hamali calculator)

All entry IDs from the original JS (`Date.now()` strings, `e_xxx` uids) are preserved so old localStorage exports remain compatible.
