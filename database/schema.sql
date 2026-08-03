-- ============================================================
-- ED Capacity Planner — PostgreSQL Schema
-- ============================================================
-- Run this file to initialize the database:
--   psql -U postgres -d ed_capacity -f schema.sql
--
-- Or inside Docker:
--   docker exec -i postgres psql -U postgres -d ed_capacity -f /schema.sql
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fuzzy name matching (QGenda sync)

-- ============================================================
-- SITES
-- ============================================================
CREATE TABLE sites (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,
    short_name      VARCHAR(20),                    -- e.g. "MSH", "MSB", "MSQ"
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sub-areas within a site (Adult ED, Peds ED, etc.)
CREATE TABLE site_areas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,           -- e.g. "Adult ED", "Peds ED"
    display_order   INTEGER NOT NULL DEFAULT 0,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PROVIDER TYPES
-- ============================================================
-- Lookup table so types are consistent and extensible
CREATE TABLE provider_types (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(50) NOT NULL UNIQUE, -- "MD","DO","PA","NP","Fellow - Med Ed", etc.
    category            VARCHAR(20) NOT NULL,        -- "Physician","APP","Fellow"
    default_fte_hours   INTEGER NOT NULL DEFAULT 1440,
    display_order       INTEGER NOT NULL DEFAULT 0
);

INSERT INTO provider_types (name, category, default_fte_hours, display_order) VALUES
    ('MD',                  'Physician', 1440, 1),
    ('DO',                  'Physician', 1440, 2),
    ('PA',                  'APP',       1440, 3),
    ('NP',                  'APP',       1440, 4),
    ('Fellow - Med Ed',     'Fellow',     900, 5),
    ('Fellow - US',         'Fellow',     900, 6),
    ('Fellow - SIM',        'Fellow',     900, 7),
    ('Fellow - Sports Med', 'Fellow',     450, 8),
    ('Fellow - Informatics','Fellow',     300, 9);

-- ============================================================
-- ROLE TYPES
-- ============================================================
CREATE TABLE role_types (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,   -- "Residency Director", "K Awardee", etc.
    category        VARCHAR(50),                    -- "Administrative","Research","Leadership"
    display_order   INTEGER NOT NULL DEFAULT 0
);

INSERT INTO role_types (name, category, display_order) VALUES
    ('Residency Director',              'Leadership',     1),
    ('Associate Residency Director',    'Leadership',     2),
    ('Assistant Residency Director',    'Leadership',     3),
    ('Medical Director',                'Leadership',     4),
    ('Associate Medical Director',      'Leadership',     5),
    ('Vice Chair',                      'Leadership',     6),
    ('Program Director',                'Leadership',     7),
    ('Fellowship Director',             'Leadership',     8),
    ('Clerkship Director',              'Leadership',     9),
    ('Nocturnist',                      'Clinical',      10),
    ('Scheduler',                       'Administrative',11),
    ('K Awardee',                       'Research',      12),
    ('Research Grant',                  'Research',      13),
    ('Med Ed',                          'Education',     14),
    ('Administrative',                  'Administrative',15),
    ('Other',                           'Other',         16);

-- ============================================================
-- PHYSICIANS / PROVIDERS
-- ============================================================
CREATE TABLE physicians (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identity
    life_no             VARCHAR(20),                         -- institutional ID (from HR / Epic)
    npi                 CHAR(10),                            -- National Provider Identifier
    last_name           VARCHAR(100) NOT NULL,
    first_name          VARCHAR(100) NOT NULL,
    email               VARCHAR(255),
    provider_type_id    INTEGER REFERENCES provider_types(id),

    -- FTE and hours
    yearly_hours        INTEGER NOT NULL DEFAULT 1440,       -- hours for 1.0 FTE (varies by type)
    clinical_pct        NUMERIC(5,4) NOT NULL DEFAULT 1.0,   -- fraction of hours that are clinical
    total_fte           NUMERIC(5,4),                        -- computed: sum of site_assignment.fte_fraction

    -- Core / home site
    core_site_id        UUID REFERENCES sites(id),

    -- Administrative / academic flags
    is_core_faculty     BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    -- Notes (free text — captures the complex arrangements in the spreadsheet)
    notes               TEXT,

    -- QGenda sync fields
    qgenda_staff_id     VARCHAR(100),                        -- QGenda internal StaffId
    qgenda_staff_key    VARCHAR(100),                        -- QGenda StaffKey (GUID)
    needs_fte_config    BOOLEAN NOT NULL DEFAULT FALSE,       -- flagged after QGenda sync if new
    last_synced_at      TIMESTAMPTZ,

    -- Term dates (for fellows with end dates)
    term_start_date     DATE,
    term_end_date       DATE,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_physicians_npi UNIQUE (npi),
    CONSTRAINT uq_physicians_life_no UNIQUE (life_no),
    CONSTRAINT chk_clinical_pct CHECK (clinical_pct >= 0 AND clinical_pct <= 1)
);

-- Fuzzy name search index for QGenda sync matching
CREATE INDEX idx_physicians_last_name_trgm ON physicians USING GIN (last_name gin_trgm_ops);
CREATE INDEX idx_physicians_npi ON physicians (npi) WHERE npi IS NOT NULL;
CREATE INDEX idx_physicians_qgenda_key ON physicians (qgenda_staff_key) WHERE qgenda_staff_key IS NOT NULL;
CREATE INDEX idx_physicians_active ON physicians (is_active);

-- ============================================================
-- SITE ASSIGNMENTS
-- (physician may be assigned to multiple sites at fractional FTE)
-- ============================================================
CREATE TABLE site_assignments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    physician_id    UUID NOT NULL REFERENCES physicians(id) ON DELETE CASCADE,
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE RESTRICT,
    fte_fraction    NUMERIC(5,4) NOT NULL,               -- e.g. 0.6 = 60% of FTE at this site
    effective_date  DATE NOT NULL DEFAULT CURRENT_DATE,  -- when this assignment started
    end_date        DATE,                                -- NULL = still active
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_fte_fraction CHECK (fte_fraction > 0 AND fte_fraction <= 1)
);

CREATE INDEX idx_site_assignments_physician ON site_assignments (physician_id);
CREATE INDEX idx_site_assignments_site ON site_assignments (site_id);
CREATE INDEX idx_site_assignments_active ON site_assignments (physician_id, site_id)
    WHERE end_date IS NULL;

-- ============================================================
-- PHYSICIAN ROLES
-- (administrative/academic roles that carry hour credits)
-- ============================================================
CREATE TABLE physician_roles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    physician_id    UUID NOT NULL REFERENCES physicians(id) ON DELETE CASCADE,
    role_type_id    INTEGER REFERENCES role_types(id),
    custom_title    VARCHAR(200),                       -- if not in role_types
    hours_credit    INTEGER NOT NULL DEFAULT 0,         -- annual hours credited toward commitment
    pct_credit      NUMERIC(5,4),                       -- alternative: express as % (e.g. 0.20 = 20%)
    effective_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date        DATE,                               -- NULL = still active
    notes           TEXT,                               -- e.g. "starting 4/1/26", "grant funded"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_physician_roles_physician ON physician_roles (physician_id);

-- ============================================================
-- LEAVE EVENTS
-- ============================================================
CREATE TABLE leaves (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    physician_id    UUID NOT NULL REFERENCES physicians(id) ON DELETE CASCADE,
    leave_type      VARCHAR(50) NOT NULL CHECK (leave_type IN (
                        'FMLA',
                        'LOA',
                        'Research Protected Time',
                        'Maternity/Paternity',
                        'Medical',
                        'Administrative',
                        'Other'
                    )),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    notes           TEXT,                               -- e.g. "K Award", "grant funded through 7/31/27"
    is_partial      BOOLEAN NOT NULL DEFAULT FALSE,     -- intermittent/partial leave
    fte_during_leave NUMERIC(5,4),                      -- effective FTE during leave (NULL = fully out)
    created_by      UUID,                               -- references users.id (added in Phase 2)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_leave_dates CHECK (end_date >= start_date)
);

CREATE INDEX idx_leaves_physician ON leaves (physician_id);
CREATE INDEX idx_leaves_dates ON leaves (start_date, end_date);
CREATE INDEX idx_leaves_type ON leaves (leave_type);

-- ============================================================
-- MONTHLY DEMAND
-- (how many clinical hours are required per site per month)
-- ============================================================
CREATE TABLE monthly_demand (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    year            SMALLINT NOT NULL,
    month           SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    hours_required  NUMERIC(8,2) NOT NULL DEFAULT 0,
    notes           TEXT,
    updated_by      UUID,                               -- references users.id
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_monthly_demand UNIQUE (site_id, year, month)
);

CREATE INDEX idx_monthly_demand_site_year ON monthly_demand (site_id, year);

-- ============================================================
-- USERS
-- (Phase 2 — authentication and role-based access)
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255),                       -- NULL if using SSO only
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer'
                        CHECK (role IN ('admin','editor','viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default admin (password: changeme — MUST change before deploying)
-- Password hash generated with: bcrypt.hash("changeme", 12)
INSERT INTO users (name, email, hashed_password, role) VALUES
    ('Admin', 'admin@yourdomain.com',
     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/HS.iK8e',
     'admin');

-- ============================================================
-- AUDIT LOG
-- (track every change — who, what, when)
-- ============================================================
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID,                               -- NULL if system action (e.g. QGenda sync)
    user_email      VARCHAR(255),                       -- denormalized for readability
    action          VARCHAR(20) NOT NULL                -- 'INSERT','UPDATE','DELETE','SYNC'
                        CHECK (action IN ('INSERT','UPDATE','DELETE','LOGIN','SYNC','EXPORT')),
    table_name      VARCHAR(50) NOT NULL,
    record_id       UUID,
    old_values      JSONB,                              -- previous state
    new_values      JSONB,                              -- new state
    ip_address      INET,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_table_record ON audit_log (table_name, record_id);
CREATE INDEX idx_audit_log_user ON audit_log (user_id);
CREATE INDEX idx_audit_log_created ON audit_log (created_at DESC);

-- ============================================================
-- QGENDA SYNC LOG
-- (track each sync run for debugging)
-- ============================================================
CREATE TABLE qgenda_sync_log (
    id              BIGSERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) CHECK (status IN ('running','success','failed')),
    providers_found INTEGER,
    providers_matched   INTEGER,
    providers_created   INTEGER,
    providers_updated   INTEGER,
    providers_flagged   INTEGER,                        -- need FTE config
    error_message   TEXT,
    raw_response_sample JSONB                           -- first record for debugging
);

-- ============================================================
-- USEFUL VIEWS
-- ============================================================

-- Active site assignments with physician and site details
CREATE VIEW v_active_assignments AS
SELECT
    sa.id,
    p.id                AS physician_id,
    p.life_no,
    p.last_name,
    p.first_name,
    p.yearly_hours,
    p.clinical_pct,
    pt.name             AS provider_type,
    pt.category         AS provider_category,
    s.id                AS site_id,
    s.name              AS site_name,
    s.short_name        AS site_short_name,
    sa.fte_fraction,
    ROUND((p.yearly_hours * sa.fte_fraction)::NUMERIC, 2)
                        AS annual_hours_at_site,
    ROUND((p.yearly_hours * sa.fte_fraction * p.clinical_pct)::NUMERIC, 2)
                        AS clinical_hours_at_site,
    sa.effective_date,
    sa.end_date
FROM site_assignments sa
JOIN physicians       p  ON p.id  = sa.physician_id
JOIN sites            s  ON s.id  = sa.site_id
LEFT JOIN provider_types pt ON pt.id = p.provider_type_id
WHERE sa.end_date IS NULL
  AND p.is_active    = TRUE
  AND s.active       = TRUE;

-- Monthly capacity summary per site
-- Call with: SELECT * FROM v_monthly_capacity WHERE year = 2026;
CREATE VIEW v_monthly_capacity AS
SELECT
    s.id                AS site_id,
    s.name              AS site_name,
    s.short_name,
    md.year,
    md.month,
    md.hours_required,
    COALESCE(
        SUM(
            (p.yearly_hours::NUMERIC / 12)
            * sa.fte_fraction
            * p.clinical_pct
        ), 0
    )                   AS clinical_hours_available,
    COALESCE(SUM(sa.fte_fraction), 0)
                        AS fte_available,
    md.hours_required -
    COALESCE(
        SUM(
            (p.yearly_hours::NUMERIC / 12)
            * sa.fte_fraction
            * p.clinical_pct
        ), 0
    )                   AS hours_gap
FROM monthly_demand md
JOIN sites            s  ON s.id  = md.site_id
LEFT JOIN site_assignments sa ON sa.site_id   = md.site_id
                              AND sa.end_date IS NULL
LEFT JOIN physicians       p  ON p.id         = sa.physician_id
                              AND p.is_active  = TRUE
GROUP BY s.id, s.name, s.short_name, md.year, md.month, md.hours_required
ORDER BY md.year, md.month, s.name;

-- Providers needing FTE configuration after QGenda sync
CREATE VIEW v_needs_fte_config AS
SELECT
    p.id,
    p.life_no,
    p.last_name,
    p.first_name,
    p.qgenda_staff_key,
    p.last_synced_at,
    p.created_at
FROM physicians p
WHERE p.needs_fte_config = TRUE
  AND p.is_active = TRUE
ORDER BY p.last_synced_at DESC;

-- ============================================================
-- TRIGGERS
-- (auto-update updated_at timestamps)
-- ============================================================
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_physicians
    BEFORE UPDATE ON physicians
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_sites
    BEFORE UPDATE ON sites
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_site_assignments
    BEFORE UPDATE ON site_assignments
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_leaves
    BEFORE UPDATE ON leaves
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- SEED DATA — Sites
-- ============================================================
INSERT INTO sites (name, short_name) VALUES
    ('Mount Sinai Hospital',        'MSH'),
    ('Mount Sinai Beth Israel',     'MSB'),
    ('Mount Sinai Queens',          'MSQ');

-- MSH areas
INSERT INTO site_areas (site_id, name, display_order)
SELECT id, 'Adult ED', 1 FROM sites WHERE short_name = 'MSH'
UNION ALL
SELECT id, 'Peds ED',  2 FROM sites WHERE short_name = 'MSH';

-- MSB and MSQ areas
INSERT INTO site_areas (site_id, name, display_order)
SELECT id, 'Adult ED', 1 FROM sites WHERE short_name = 'MSB';
INSERT INTO site_areas (site_id, name, display_order)
SELECT id, 'Adult ED', 1 FROM sites WHERE short_name = 'MSQ';

-- ============================================================
-- SEED DATA — Sample monthly demand (MSH 2026)
-- ============================================================
INSERT INTO monthly_demand (site_id, year, month, hours_required)
SELECT
    s.id,
    2026,
    m.month,
    CASE
        WHEN s.short_name = 'MSH' AND m.month IN (2,4,6,9,11) THEN 440
        WHEN s.short_name = 'MSH'                              THEN 480
        WHEN s.short_name = 'MSB' AND m.month IN (2,4,6,9,11) THEN 290
        WHEN s.short_name = 'MSB'                              THEN 320
        WHEN s.short_name = 'MSQ' AND m.month IN (2,4,6,9,11) THEN 220
        WHEN s.short_name = 'MSQ'                              THEN 240
    END
FROM sites s
CROSS JOIN (
    SELECT generate_series(1,12) AS month
) m
WHERE s.active = TRUE;

-- ============================================================
-- HELPFUL QUERIES (reference — not executed)
-- ============================================================

/*

-- Monthly capacity for 2026 at MSH (ignores leave — add leave logic in app layer)
SELECT month, clinical_hours_available, hours_required, hours_gap
FROM v_monthly_capacity
WHERE year = 2026 AND short_name = 'MSH'
ORDER BY month;

-- All active providers at MSH with their clinical hours
SELECT last_name, first_name, provider_type, fte_fraction,
       clinical_hours_at_site, annual_hours_at_site
FROM v_active_assignments
WHERE site_short_name = 'MSH'
ORDER BY last_name;

-- Providers on leave in a given month (example: March 2026)
SELECT p.last_name, p.first_name, l.leave_type, l.start_date, l.end_date
FROM leaves l
JOIN physicians p ON p.id = l.physician_id
WHERE l.start_date <= '2026-03-31'
  AND l.end_date   >= '2026-03-01'
ORDER BY p.last_name;

-- Providers needing FTE config after QGenda sync
SELECT last_name, first_name, qgenda_staff_key, last_synced_at
FROM v_needs_fte_config;

-- Recent audit trail
SELECT created_at, user_email, action, table_name, notes
FROM audit_log
ORDER BY created_at DESC
LIMIT 50;

*/
