-- VEHDiag — initial schema (PostgreSQL 14+)
-- Applied in order by scripts/migrate.js; every migration runs in its own
-- transaction and is recorded in schema_migrations.

BEGIN;

CREATE TABLE users (
    id            UUID PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'USER'
                  CHECK (role IN ('USER', 'TECHNICIAN', 'WORKSHOP_ADMIN', 'ADMIN', 'SUPER_ADMIN')),
    password_hash TEXT NOT NULL,
    is_demo       BOOLEAN NOT NULL DEFAULT FALSE,
    settings      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vehicles (
    id            UUID PRIMARY KEY,
    "userId"      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    vin           TEXT,
    manufacturer  TEXT,
    model         TEXT,
    year          INTEGER,
    engine        TEXT,
    fuel_type     TEXT,
    transmission  TEXT,
    "mileageKm"   INTEGER,
    plate         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vehicles_user ON vehicles ("userId");

CREATE TABLE sessions (
    id            UUID PRIMARY KEY,
    "userId"      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    "vehicleId"   UUID REFERENCES vehicles (id) ON DELETE SET NULL,
    "profileId"   TEXT NOT NULL,
    "profileName" TEXT,
    status        TEXT NOT NULL DEFAULT 'created'
                  CHECK (status IN ('created', 'scanning', 'completed', 'failed')),
    progress      INTEGER NOT NULL DEFAULT 0,
    stage         TEXT,
    error         TEXT,
    scan          JSONB,
    events        JSONB NOT NULL DEFAULT '[]'::jsonb,
    "dtcCount"    INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_user ON sessions ("userId");
CREATE INDEX idx_sessions_status ON sessions (status);

CREATE TABLE reports (
    id                  UUID PRIMARY KEY,
    "sessionId"         UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    "userId"            UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    template            TEXT NOT NULL DEFAULT 'classic',
    technician          TEXT,
    "diagnosticStatus"  TEXT NOT NULL,
    "storedDtcCount"    INTEGER NOT NULL DEFAULT 0,
    "pendingDtcCount"   INTEGER NOT NULL DEFAULT 0,
    dtcs                JSONB NOT NULL DEFAULT '[]'::jsonb,
    vehicle             JSONB,
    recommendations     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_user ON reports ("userId");
CREATE INDEX idx_reports_session ON reports ("sessionId");

CREATE TABLE devices (
    id            UUID PRIMARY KEY,
    "userId"      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN
                  ('elm327-bluetooth', 'elm327-usb', 'elm327-wifi',
                   'can-socketcan', 'can-pcan', 'can-kvaser', 'can-vector',
                   'simulator')),
    address       TEXT,
    status        TEXT NOT NULL DEFAULT 'registered',
    "pairedAt"    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_devices_user ON devices ("userId");

CREATE TABLE subscriptions (
    id            UUID PRIMARY KEY,
    "userId"      UUID NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    plan          TEXT NOT NULL CHECK (plan IN ('free', 'pro', 'workshop')),
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    "selectedAt"  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id            UUID PRIMARY KEY,
    "userId"      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type          TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    "sessionId"   UUID,
    read          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_user ON notifications ("userId", created_at DESC);

CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    "actorId"   UUID,
    action      TEXT NOT NULL,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_audit_ts ON audit_log (ts DESC);

COMMIT;
