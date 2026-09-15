-- ============================================================
-- Migration: Phase 1.5 (auth / audit log / error log) + Phase D
-- (time allocations)
-- ============================================================
-- database/schema.sql only runs automatically against an EMPTY Postgres
-- data directory (docker-entrypoint-initdb.d behavior) — it will NOT touch
-- an already-initialized database. This file brings an existing database
-- (e.g. the live Coolify deployment) up to date with everything schema.sql
-- now describes, without touching data in tables that already exist.
--
-- Written to be safe to run more than once (IF NOT EXISTS / guarded DO
-- blocks throughout) and safe to run against a database that already has
-- some-but-not-all of this applied.
--
-- Run it with:
--   psql "$DATABASE_URL" -f database/migrations/2026_phase1_5_and_phase_d.sql
-- or inside the Coolify postgres container:
--   docker exec -i <postgres_container> psql -U postgres -d ed_capacity \
--     < database/migrations/2026_phase1_5_and_phase_d.sql
--
-- BACK UP THE DATABASE FIRST (e.g. `pg_dump`) — this is DDL against a live
-- production database and, while every step here is additive, DDL on a
-- production DB should never run without a fresh backup on hand.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── USERS (Phase 1.5) ───────────────────────────────────────────────────────
-- Full CREATE in case this database predates the users table entirely.
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255),
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer'
                        CHECK (role IN ('admin','editor','viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- physician_id: set for accounts tied to one provider; NULL for admin-only accounts.
ALTER TABLE users ADD COLUMN IF NOT EXISTS physician_id UUID REFERENCES physicians(id);

-- Widen the role CHECK to include 'provider'. CHECK constraints can't be
-- ALTERed in place, so drop-and-recreate. Guarded: only acts if a
-- constraint by this name exists and doesn't already allow 'provider'.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_role_check' AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users DROP CONSTRAINT users_role_check;
    END IF;
    ALTER TABLE users ADD CONSTRAINT users_role_check
        CHECK (role IN ('admin','editor','viewer','provider'));
EXCEPTION WHEN duplicate_object THEN
    NULL; -- constraint already matches; nothing to do
END $$;

-- ── AUDIT LOG (Phase 1.5) ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID,
    user_email      VARCHAR(255),
    action          VARCHAR(20) NOT NULL
                        CHECK (action IN ('INSERT','UPDATE','DELETE','LOGIN','SYNC','EXPORT')),
    table_name      VARCHAR(50) NOT NULL,
    record_id       UUID,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_table_record ON audit_log (table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at DESC);

-- ── ERROR LOG (Phase 1.5) ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS error_log (
    id              BIGSERIAL PRIMARY KEY,
    error_id        VARCHAR(32) NOT NULL UNIQUE,
    method          VARCHAR(10) NOT NULL,
    path            VARCHAR(500) NOT NULL,
    exception_type  VARCHAR(200) NOT NULL,
    message         TEXT NOT NULL,
    traceback       TEXT NOT NULL,
    user_id         UUID,
    user_email      VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_error_log_created ON error_log (created_at DESC);

-- ── PHYSICIANS / SITE ASSIGNMENTS / ROLES (Phase D columns) ─────────────────
-- Defaults TRUE: every existing physician has zero time_allocations rows
-- until configured, so they genuinely need configuring.
ALTER TABLE physicians ADD COLUMN IF NOT EXISTS
    needs_time_allocation_config BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE site_assignments ADD COLUMN IF NOT EXISTS change_reason TEXT;
ALTER TABLE physician_roles ADD COLUMN IF NOT EXISTS change_reason TEXT;

-- ── TIME CATEGORIES (Phase D) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS time_categories (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,
    is_clinical     BOOLEAN NOT NULL,
    display_order   INTEGER NOT NULL
);

INSERT INTO time_categories (name, is_clinical, display_order) VALUES
    ('Adult ED',    TRUE,   1),
    ('Peds ED',     TRUE,   2),
    ('P2P',         TRUE,   3),
    ('VUC',         TRUE,   4),
    ('IHS',         TRUE,   5),
    ('Elmhurst',    TRUE,   6),
    ('Admin',       FALSE,  7),
    ('Nocturnist',  FALSE,  8),
    ('Teaching',    FALSE,  9),
    ('Research',    FALSE, 10)
ON CONFLICT (name) DO NOTHING;

-- ── TIME ALLOCATIONS (Phase D) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS time_allocations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    physician_id      UUID NOT NULL REFERENCES physicians(id) ON DELETE CASCADE,
    site_id           UUID REFERENCES sites(id),
    time_category_id  INTEGER NOT NULL REFERENCES time_categories(id),
    year              INTEGER NOT NULL,
    month             INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    hours             NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (hours >= 0),
    change_reason     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_time_allocation UNIQUE (physician_id, site_id, time_category_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_time_allocations_physician_year ON time_allocations (physician_id, year);

COMMIT;

-- ── After this runs ──────────────────────────────────────────────────────────
-- If this database has no admin user yet (e.g. the old hardcoded-hash seed
-- row from an earlier schema.sql was never applied here), create one from
-- the backend/ directory:
--   ADMIN_EMAIL=you@yourdomain.com ADMIN_PASSWORD='...' python -m scripts.create_admin
