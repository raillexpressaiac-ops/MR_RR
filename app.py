"""
SRPS Cargo - Flask + SQLite Backend
========================================
Combines two systems:
  1. MR Management  (Online GST + Offline MR entries)
  2. RR Manager     (Hamali calculator with per-train bag rate)

All UI logic preserved from original HTML files; data is now stored
in SQLite instead of localStorage.
"""

import os
import time
import random
import sqlite3
from datetime import date, datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------------------
# App setup
# ----------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "srps_cargo.db")


def get_conn():
    """Open a fresh sqlite3 connection with FK enforcement on."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    # Enforce foreign keys (ON DELETE CASCADE etc.)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Apply schema.sql safely.

    The schema uses CREATE TABLE IF NOT EXISTS and INSERT OR IGNORE,
    so running this on every startup is harmless and will NOT delete
    existing user data. Only missing tables/seed rows get created.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        print("[init_db] schema.sql not found, skipping.")
        return

    db_existed = os.path.exists(DB_PATH)
    conn = get_conn()
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
        if db_existed:
            print("[init_db] DB already exists — schema verified, data preserved.")
        else:
            print("[init_db] Fresh DB created with seed data.")
    except Exception as e:
        print(f"[init_db] Schema apply failed: {e}")
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def row_to_dict(row):
    """Turn a sqlite3 Row into a JSON-friendly dict."""
    if row is None:
        return None
    out = {}
    for k in row.keys():
        v = row[k]
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()[:10] if isinstance(v, date) and not isinstance(v, datetime) else v.isoformat()
        else:
            out[k] = v
    return out


def gen_mr_id():
    """Same shape as JS Date.now().toString() - 13-digit timestamp ms."""
    return str(int(time.time() * 1000))


def gen_rr_id():
    """Mirror JS uid(): 'e_' + base36(time) + 5 random chars"""
    t36 = ""
    n = int(time.time() * 1000)
    while n > 0:
        t36 = "0123456789abcdefghijklmnopqrstuvwxyz"[n % 36] + t36
        n //= 36
    rand = "".join(random.choice("0123456789abcdefghijklmnopqrstuvwxyz") for _ in range(5))
    return f"e_{t36}{rand}"


# ============================================================
# ROUTES — Page Rendering
# ============================================================
@app.route("/")
def home():
    return redirect(url_for("mr_system"))


@app.route("/mr")
def mr_system():
    """SRPS MR Management page (online GST + offline MR)."""
    return render_template("mr_system.html")


@app.route("/rr")
def rr_manager():
    """SRPS RR Manager page (Hamali calculator)."""
    return render_template("rr_manager.html")


# ============================================================
# API — MR SYSTEM: Trains
# ============================================================
@app.route("/api/mr/trains", methods=["GET"])
def mr_trains_list():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mr_trains ORDER BY mode DESC, name ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Reshape into the shape the front-end JS expects:
    # { no, name, mode, contract, fixed: {...} }
    trains = []
    for r in rows:
        d = row_to_dict(r)
        if d["mode"] == "online":
            fixed = {
                "taxable":      d["fixed_taxable"],
                "cgst":         d["fixed_cgst"],
                "sgst":         d["fixed_sgst"],
                "igst":         d["fixed_igst"],
                "total_supply": d["fixed_total_supply"],
            }
        else:
            fixed = {
                "weight": d["fixed_weight"],
                "gst":    d["fixed_gst"],
                "mr_amt": d["fixed_mr_amt"],
                "total":  d["fixed_total"],
                "pmode":  d["fixed_pmode"],
            }
        trains.append({
            "no":       d["no"],
            "name":     d["name"],
            "mode":     d["mode"],
            "contract": d["contract"],
            "fixed":    fixed,
        })
    return jsonify(trains)


@app.route("/api/mr/trains", methods=["POST"])
def mr_train_create():
    data = request.get_json(force=True)
    no       = (data.get("no") or "").strip()
    name     = (data.get("name") or "").strip()
    mode     = data.get("mode")
    contract = (data.get("contract") or "").strip()

    if not no or not name or mode not in ("online", "offline"):
        return jsonify({"error": "Train no, name and valid mode are required"}), 400

    conn = get_conn()
    cur = conn.cursor()
    try:
        if mode == "online":
            cur.execute("""
                INSERT INTO mr_trains (no, name, mode, contract,
                    fixed_taxable, fixed_cgst, fixed_sgst, fixed_igst, fixed_total_supply)
                VALUES (?,?,?,?, 0,0,0,0,0)
            """, (no, name, mode, contract))
        else:
            cur.execute("""
                INSERT INTO mr_trains (no, name, mode, contract,
                    fixed_weight, fixed_gst, fixed_mr_amt, fixed_total, fixed_pmode)
                VALUES (?,?,?,?, '4 TON', 0, 0, 0, 'CASH')
            """, (no, name, mode, contract))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({"error": f"Train number '{no}' already exists"}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"status": "ok"}), 201


@app.route("/api/mr/trains/<path:train_no>", methods=["DELETE"])
def mr_train_delete(train_no):
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Kept entries by design — only block deletion if FK constraint hit
        cur.execute("DELETE FROM mr_trains WHERE no = ?", (train_no,))
        conn.commit()
    except Exception as e:
        if "FOREIGN KEY constraint failed" in str(e):
            conn.rollback()
            return jsonify({"error": "This train has entries; remove them first."}), 409
        else:
            raise
    finally:
        cur.close()
        conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# API — MR SYSTEM: Entries
# ============================================================
@app.route("/api/mr/entries", methods=["GET"])
def mr_entries_list():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mr_entries ORDER BY entry_date DESC, created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Reshape rows so the JS sees the same field names it uses:
    out = []
    for r in rows:
        d = row_to_dict(r)
        out.append({
            "id":           d["id"],
            "date":         d["entry_date"],          # JS uses .date
            "train_no":     d["train_no"],
            "mode":         d["mode"],
            "contract":     d["contract"],
            "space":        d["space"],
            "penalty":      d["penalty"],
            "issue_date":   d["issue_date"],
            # ONLINE
            "invoice":            d["invoice"],
            "service_date":       d["service_date"],
            "taxable":            d["taxable"],
            "cgst":               d["cgst"],
            "sgst":               d["sgst"],
            "igst":               d["igst"],
            "total_value_supply": d["total_value_supply"],
            # OFFLINE
            "side":   d["side"],
            "mr":     d["mr"],
            "weight": d["weight"],
            "gst":    d["gst"],
            "mramt":  d["mramt"],
            "total":  d["total"],
            "pmode":  d["pmode"],
            "remark": d["remark"],
        })
    return jsonify(out)


@app.route("/api/mr/entries", methods=["POST"])
def mr_entry_save():
    """Upsert a single entry. Replaces matching id, else inserts new."""
    e = request.get_json(force=True)

    entry_id = e.get("id") or gen_mr_id()
    mode = e.get("mode")
    if mode not in ("online", "offline"):
        return jsonify({"error": "mode must be 'online' or 'offline'"}), 400

    common = {
        "id":         entry_id,
        "entry_date": e.get("date"),
        "train_no":   e.get("train_no"),
        "mode":       mode,
        "contract":   e.get("contract"),
        "space":      e.get("space"),
        "penalty":    float(e.get("penalty") or 0),
        "issue_date": e.get("issue_date") or None,
    }

    if mode == "online":
        specific = {
            "invoice":            e.get("invoice") or None,
            "service_date":       e.get("service_date") or None,
            "taxable":            float(e.get("taxable") or 0),
            "cgst":               float(e.get("cgst") or 0),
            "sgst":               float(e.get("sgst") or 0),
            "igst":               float(e.get("igst") or 0),
            "total_value_supply": float(e.get("total_value_supply") or 0),
            "side": None, "mr": None, "weight": None, "gst": 0,
            "mramt": 0, "total": 0, "pmode": None, "remark": None,
        }
    else:
        specific = {
            "invoice": None, "service_date": None,
            "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_value_supply": 0,
            "side":   e.get("side"),
            "mr":     e.get("mr") or None,
            "weight": e.get("weight"),
            "gst":    float(e.get("gst") or 0),
            "mramt":  float(e.get("mramt") or 0),
            "total":  float(e.get("total") or 0),
            "pmode":  e.get("pmode"),
            "remark": e.get("remark"),
        }

    payload = {**common, **specific}

    conn = get_conn()
    cur = conn.cursor()
    try:
        # SQLite doesn't support ON CONFLICT with multiple columns, so we use INSERT OR REPLACE
        cur.execute("""
            INSERT OR REPLACE INTO mr_entries (
                id, entry_date, train_no, mode, contract, space, penalty, issue_date,
                invoice, service_date, taxable, cgst, sgst, igst, total_value_supply,
                side, mr, weight, gst, mramt, total, pmode, remark, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
            )
        """, (
            payload["id"], payload["entry_date"], payload["train_no"], payload["mode"],
            payload["contract"], payload["space"], payload["penalty"], payload["issue_date"],
            payload["invoice"], payload["service_date"], payload["taxable"], payload["cgst"],
            payload["sgst"], payload["igst"], payload["total_value_supply"],
            payload["side"], payload["mr"], payload["weight"], payload["gst"],
            payload["mramt"], payload["total"], payload["pmode"], payload["remark"]
        ))
        conn.commit()
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({"status": "ok", "id": entry_id})


@app.route("/api/mr/entries/<entry_id>", methods=["DELETE"])
def mr_entry_delete(entry_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM mr_entries WHERE id = ?", (entry_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# API — RR MANAGER: Trains
# ============================================================
@app.route("/api/rr/trains", methods=["GET"])
def rr_trains_list():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rate FROM rr_trains ORDER BY created_at ASC")
    rows = [row_to_dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/rr/trains", methods=["POST"])
def rr_train_create():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    rate = data.get("rate")

    if not name:
        return jsonify({"error": "Station name required"}), 400
    try:
        rate = int(rate)
        if rate <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Valid rate required"}), 400

    # Mirror the JS id generation
    safe = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
    suffix = "".join(random.choice("0123456789abcdefghijklmnopqrstuvwxyz") for _ in range(3))
    new_id = f"{safe}_{suffix}"

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO rr_trains (id, name, rate) VALUES (?, ?, ?)",
            (new_id, name, rate)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({"error": "Train already exists"}), 409
    finally:
        cur.close()
        conn.close()

    return jsonify({"id": new_id, "name": name, "rate": rate}), 201


@app.route("/api/rr/trains/<train_id>", methods=["DELETE"])
def rr_train_delete(train_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM rr_trains WHERE id = ?", (train_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# API — RR MANAGER: Entries
# ============================================================
@app.route("/api/rr/entries", methods=["GET"])
def rr_entries_list():
    """Return entries grouped by train_id, matching JS shape: { train_id: [entries...] }."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM rr_entries
        ORDER BY entry_date DESC, created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    grouped = {}
    for r in rows:
        d = row_to_dict(r)
        train_id = d["train_id"]
        grouped.setdefault(train_id, []).append({
            "id":        d["id"],
            "date":      d["entry_date"],
            "rrNo":      d["rr_no"],
            "from":      d["from_station"],
            "consignor": d["consignor"],
            "to":        d["to_station"],
            "consignee": d["consignee"],
            "bag":       d["bag"],
            "gst":       d["gst"],
            "rrAmt":     d["rr_amt"],
            "weight":    d["weight"],
            "rate":      d["rate"],
            "hamali":    d["hamali"],
            "total":     d["total"],
        })
    return jsonify(grouped)


@app.route("/api/rr/entries", methods=["POST"])
def rr_entry_save():
    e = request.get_json(force=True)
    train_id = e.get("train_id")
    if not train_id:
        return jsonify({"error": "train_id required"}), 400

    rr_no = (e.get("rrNo") or "").strip()
    if not rr_no:
        return jsonify({"error": "RR No is required"}), 400

    bag    = int(e.get("bag") or 0)
    rr_amt = float(e.get("rrAmt") or 0)
    rate   = int(e.get("rate") or 0)
    hamali = bag * rate
    total  = rr_amt + hamali

    entry_id = e.get("id") or gen_rr_id()

    payload = {
        "id":           entry_id,
        "train_id":     train_id,
        "entry_date":   e.get("date") or date.today().isoformat(),
        "rr_no":        rr_no,
        "from_station": (e.get("from") or "").strip() or None,
        "consignor":    (e.get("consignor") or "").strip() or None,
        "to_station":   (e.get("to") or "").strip() or None,
        "consignee":    (e.get("consignee") or "").strip() or None,
        "bag":          bag,
        "gst":          (e.get("gst") or "").strip() or None,
        "rr_amt":       rr_amt,
        "weight":       float(e.get("weight") or 0),
        "rate":         rate,
        "hamali":       hamali,
        "total":        total,
    }

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT OR REPLACE INTO rr_entries (
                id, train_id, entry_date, rr_no, from_station, consignor,
                to_station, consignee, bag, gst, rr_amt, weight, rate, hamali, total, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, CURRENT_TIMESTAMP
            )
        """, (
            payload["id"], payload["train_id"], payload["entry_date"], payload["rr_no"],
            payload["from_station"], payload["consignor"], payload["to_station"],
            payload["consignee"], payload["bag"], payload["gst"],
            payload["rr_amt"], payload["weight"], payload["rate"], payload["hamali"],
            payload["total"]
        ))
        conn.commit()
    except Exception as ex:
        conn.rollback()
        if "FOREIGN KEY constraint failed" in str(ex):
            return jsonify({"error": "Invalid train_id"}), 400
        else:
            return jsonify({"error": str(ex)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({"status": "ok", "id": entry_id})


@app.route("/api/rr/entries/<entry_id>", methods=["DELETE"])
def rr_entry_delete(entry_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM rr_entries WHERE id = ?", (entry_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# Health
# ============================================================
@app.route("/api/health")
def health():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as ex:
        return jsonify({"status": "error", "db": str(ex)}), 500


# ----------------------------------------------------------------------------
# Always run init_db when the module loads so gunicorn (and __main__) both
# get a fully initialised database on startup. Safe to run repeatedly —
# schema uses CREATE TABLE IF NOT EXISTS and INSERT OR IGNORE.
init_db()

if __name__ == "__main__":
    # Local dev only — gunicorn is used in production (see Procfile).
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)