-- ============================================================================
-- CivicLens Phase 16 Extension: Authentication & Multi-User Schema (0002_auth.sql)
-- Architecture: Sessions, credentials, security events, and ownership isolation.
-- ============================================================================

-- Disable foreign keys temporarily during table rebuilds
PRAGMA foreign_keys = OFF;

-- 1. Citizens & Users Table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL CHECK(length(full_name) >= 1 AND length(full_name) <= 100),
    email TEXT NOT NULL,
    email_normalized TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    email_verified INTEGER NOT NULL DEFAULT 0 CHECK(email_verified IN (0, 1)),
    preferred_language TEXT NOT NULL DEFAULT 'en' CHECK(preferred_language IN ('en', 'ta')),
    terms_version TEXT NOT NULL,
    terms_accepted_at TEXT NOT NULL,
    password_changed_at TEXT,
    last_login_at TEXT,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email_norm ON users (email_normalized);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_created ON users (created_at DESC);

-- 2. Authenticated Sessions Table (Opaque random token in HttpOnly cookie; token_hash stored)
CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    idle_expires_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    remember_me INTEGER NOT NULL DEFAULT 0 CHECK(remember_me IN (0, 1)),
    user_agent TEXT,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON auth_sessions (token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_idle_exp ON auth_sessions (idle_expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_abs_exp ON auth_sessions (absolute_expires_at);

-- 3. Password Reset Tokens Table (Expiring, single-use, max 3 active per user)
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    requested_ip_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_user_id ON password_reset_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_token_hash ON password_reset_tokens (token_hash);

-- 4. Authentication Security Audit Events (Zero plaintext emails, passwords, tokens, or raw IPs)
CREATE TABLE IF NOT EXISTS auth_events (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ip_hash TEXT,
    user_agent_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_events_user_id ON auth_events (user_id);
CREATE INDEX IF NOT EXISTS idx_auth_events_created ON auth_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_events_type ON auth_events (event_type);

-- 5. Persistent Authentication Throttle & Lockout Table
CREATE TABLE IF NOT EXISTS auth_throttle (
    key_hash TEXT PRIMARY KEY,
    window_start TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_throttle_locked ON auth_throttle (locked_until);

-- ============================================================================
-- 6. Table Rebuilds for Multi-User Ownership
-- ============================================================================

-- 6.1 Rebuild 'documents' table to allow separate users to upload identical PDFs:
-- Change UNIQUE(collection, sha256) -> UNIQUE(owner_id, collection, sha256)
CREATE TABLE IF NOT EXISTS documents_new (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    collection TEXT NOT NULL DEFAULT 'user',
    filename TEXT NOT NULL,
    display_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    language TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'processing',
    progress TEXT,
    error_message TEXT,
    warnings TEXT DEFAULT '[]',
    index_status TEXT NOT NULL DEFAULT 'not_indexed',
    index_model TEXT,
    index_built_at TEXT,
    index_chunk_count INTEGER NOT NULL DEFAULT 0,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    total_chars INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    summaries TEXT DEFAULT '{}',
    relative_path TEXT,
    file_missing INTEGER NOT NULL DEFAULT 0,
    
    title TEXT,
    issuing_authority TEXT,
    source_url TEXT,
    publication_date TEXT,
    effective_date TEXT,
    series_id TEXT,
    source_status TEXT DEFAULT 'current',
    superseded_by TEXT REFERENCES documents_new(id) ON DELETE SET NULL,
    notes TEXT,
    library_added_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    UNIQUE(owner_id, collection, sha256)
);

-- Copy all existing records
INSERT OR IGNORE INTO documents_new SELECT * FROM documents;
DROP TABLE documents;
ALTER TABLE documents_new RENAME TO documents;

CREATE INDEX IF NOT EXISTS idx_documents_collection_created ON documents (collection, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_owner_created ON documents (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
CREATE INDEX IF NOT EXISTS idx_documents_series_id ON documents (series_id);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents (sha256);

-- 6.2 Rebuild 'preferences' table:
-- Change PRIMARY KEY (key) -> PRIMARY KEY (owner_id, key)
CREATE TABLE IF NOT EXISTS preferences_new (
    owner_id TEXT NOT NULL DEFAULT 'local',
    key TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
);

INSERT OR IGNORE INTO preferences_new (owner_id, key, value, updated_at)
SELECT 'local', key, value, updated_at FROM preferences;
DROP TABLE preferences;
ALTER TABLE preferences_new RENAME TO preferences;

-- 6.3 Composite Indexes for Multi-User Queries on Existing Tables
CREATE INDEX IF NOT EXISTS idx_comparisons_owner_created ON comparisons (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_verifications_owner_created ON verifications (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guides_owner_created ON service_guides (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_form_fields_owner ON form_field_explanations (owner_id);
CREATE INDEX IF NOT EXISTS idx_grievances_owner_created ON grievances (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_browser_sessions_owner_created ON browser_sessions (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_owner_updated ON conversations (owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_runs_owner_created ON tool_runs (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approvals_owner_created ON approvals (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_owner_created ON activity (owner_id, created_at DESC);

-- Re-enable foreign key constraints
PRAGMA foreign_keys = ON;
