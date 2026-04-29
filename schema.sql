-- ============================================================
-- SRPS CARGO - PostgreSQL Schema
-- Two systems: MR Management + RR Manager (Hamali)
--
-- NOTE: This script is SAFE to run multiple times.
--       Uses CREATE TABLE IF NOT EXISTS and ON CONFLICT DO NOTHING
--       so existing data is always preserved.
-- ============================================================

-- ============================================================
-- SYSTEM 1: MR MANAGEMENT (Online GST + Offline MR)
-- ============================================================

CREATE TABLE IF NOT EXISTS mr_trains (
    no              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    mode            TEXT NOT NULL,
    contract        TEXT,

    fixed_taxable       REAL DEFAULT 0,
    fixed_cgst          REAL DEFAULT 0,
    fixed_sgst          REAL DEFAULT 0,
    fixed_igst          REAL DEFAULT 0,
    fixed_total_supply  REAL DEFAULT 0,

    fixed_weight    TEXT DEFAULT '4 TON',
    fixed_gst       REAL DEFAULT 0,
    fixed_mr_amt    REAL DEFAULT 0,
    fixed_total     REAL DEFAULT 0,
    fixed_pmode     TEXT DEFAULT 'CASH',

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mr_entries (
    id              TEXT PRIMARY KEY,
    entry_date      DATE NOT NULL,
    train_no        TEXT NOT NULL REFERENCES mr_trains(no) ON DELETE CASCADE,
    mode            TEXT NOT NULL,
    contract        TEXT,
    space           TEXT,
    penalty         REAL DEFAULT 0,
    issue_date      DATE,

    invoice         TEXT,
    service_date    DATE,
    taxable         REAL DEFAULT 0,
    cgst            REAL DEFAULT 0,
    sgst            REAL DEFAULT 0,
    igst            REAL DEFAULT 0,
    total_value_supply REAL DEFAULT 0,

    side            TEXT,
    mr              TEXT,
    weight          TEXT,
    gst             REAL DEFAULT 0,
    mramt           REAL DEFAULT 0,
    total           REAL DEFAULT 0,
    pmode           TEXT,
    remark          TEXT,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mr_entries_date  ON mr_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_mr_entries_train ON mr_entries(train_no);
CREATE INDEX IF NOT EXISTS idx_mr_entries_mode  ON mr_entries(mode);

-- ============================================================
-- SYSTEM 2: RR MANAGER (Hamali calculator)
-- ============================================================

CREATE TABLE IF NOT EXISTS rr_trains (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    rate            INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rr_entries (
    id              TEXT PRIMARY KEY,
    train_id        TEXT NOT NULL REFERENCES rr_trains(id) ON DELETE CASCADE,
    entry_date      DATE NOT NULL,
    rr_no           TEXT NOT NULL,
    from_station    TEXT,
    consignor       TEXT,
    to_station      TEXT,
    consignee       TEXT,
    bag             INTEGER DEFAULT 0,
    gst             TEXT,
    rr_amt          REAL DEFAULT 0,
    weight          REAL DEFAULT 0,
    rate            INTEGER NOT NULL,
    hamali          REAL DEFAULT 0,
    total           REAL DEFAULT 0,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rr_entries_train ON rr_entries(train_id);
CREATE INDEX IF NOT EXISTS idx_rr_entries_date  ON rr_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_rr_entries_rrno  ON rr_entries(rr_no);

-- ============================================================
-- SEED DATA — defaults from the original HTML files
-- ON CONFLICT DO NOTHING means re-running won't duplicate rows
-- ============================================================

-- MR System default trains (ONLINE GST)
INSERT INTO mr_trains (no, name, mode, contract, fixed_taxable, fixed_cgst, fixed_sgst, fixed_igst, fixed_total_supply) VALUES
  ('19037',     'Bandra Avadh',        'online', 'CON-101', 34323.00,  858.08, 858.08, 0.00, 36040.00),
  ('22901 SLR', 'Bandra Udaipur SLR',  'online', 'CON-102',  5572.44,  139.31, 139.31, 0.00,  5852.00),
  ('22975 F1',  'Bandra Ramnagar F1',  'online', 'CON-103',  7442.00,  436.05, 436.05, 0.00, 18315.00),
  ('22975 R1',  'Bandra Ramnagar R1',  'online', 'CON-104', 15912.00,  397.80, 397.80, 0.00, 16708.00),
  ('14313',     'Bandra Bareilly',     'online', 'CON-105', 10305.06,  257.63, 257.63, 0.00, 10821.00)
ON CONFLICT (no) DO NOTHING;

-- MR System default trains (OFFLINE MR)
INSERT INTO mr_trains (no, name, mode, contract, fixed_weight, fixed_gst, fixed_mr_amt, fixed_total, fixed_pmode) VALUES
  ('22444', 'Kanpur',  'offline', 'CON-201', '3.9 TON', 339, 6768, 7107, 'CASH'),
  ('22901', 'Udaipur', 'offline', 'CON-202', '3.9 TON', 362, 7221, 7583, 'CASH'),
  ('12995', 'Ajmer',   'offline', 'CON-203', '4 TON',   404, 8079, 8483, 'CASH'),
  ('12480', 'Jodhpur', 'offline', 'CON-204', '4 TON',   421, 8416, 8837, 'CASH')
ON CONFLICT (no) DO NOTHING;

-- RR Manager default trains
INSERT INTO rr_trains (id, name, rate) VALUES
  ('kanpur',      'Kanpur',      68),
  ('indore',      'Indore',      12),
  ('kota',        'Kota',        70),
  ('chittorgarh', 'Chittorgarh', 62),
  ('ajmer',       'Ajmer',       50),
  ('udaipur',     'Udaipur',     50),
  ('jodhpur',     'Jodhpur',     80),
  ('bikaner',     'Bikaner',     70)
ON CONFLICT (id) DO NOTHING;
