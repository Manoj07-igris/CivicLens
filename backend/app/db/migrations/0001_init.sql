-- ============================================================================
-- CivicLens Phase 15: Unified Database Schema Migration (0001_init.sql)
-- Architecture: Single SQLite database with WAL mode and foreign key cascades.
-- ============================================================================

-- 1. Documents & Official Sources
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    collection TEXT NOT NULL DEFAULT 'user', -- 'user' | 'official'
    filename TEXT NOT NULL,
    display_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    language TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'processing', -- 'processing' | 'ready' | 'ready_with_warnings' | 'failed'
    progress TEXT, -- JSON {"current_page": N, "total_pages": N}
    error_message TEXT,
    warnings TEXT DEFAULT '[]', -- JSON string array
    index_status TEXT NOT NULL DEFAULT 'not_indexed', -- 'not_indexed' | 'indexing' | 'indexed' | 'failed'
    index_model TEXT,
    index_built_at TEXT,
    index_chunk_count INTEGER NOT NULL DEFAULT 0,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    total_chars INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    summaries TEXT DEFAULT '{}', -- JSON {"en": "...", "ta": "..."}
    relative_path TEXT,
    file_missing INTEGER NOT NULL DEFAULT 0,
    
    -- Official Source Library extension fields
    title TEXT,
    issuing_authority TEXT,
    source_url TEXT,
    publication_date TEXT,
    effective_date TEXT,
    series_id TEXT,
    source_status TEXT DEFAULT 'current', -- 'current' | 'superseded' | 'unknown'
    superseded_by TEXT REFERENCES documents(id) ON DELETE SET NULL,
    notes TEXT,
    library_added_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    UNIQUE(collection, sha256)
);

CREATE INDEX IF NOT EXISTS idx_documents_collection_created ON documents (collection, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
CREATE INDEX IF NOT EXISTS idx_documents_series_id ON documents (series_id);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents (sha256);

-- 2. Document Pages
CREATE TABLE IF NOT EXISTS document_pages (
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    char_count INTEGER NOT NULL DEFAULT 0,
    method TEXT NOT NULL DEFAULT 'direct_text',
    quality TEXT NOT NULL DEFAULT 'good',
    PRIMARY KEY (document_id, page_number)
);

-- 3. Document Chunks
CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    start_offset INTEGER NOT NULL DEFAULT 0,
    end_offset INTEGER NOT NULL DEFAULT 0,
    method TEXT NOT NULL DEFAULT 'direct_text'
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_page ON document_chunks (document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_index ON document_chunks (document_id, chunk_index);

-- 4. Official Government Portals Registry
CREATE TABLE IF NOT EXISTS portals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    name_ta TEXT,
    url TEXT NOT NULL,
    department TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'state',
    description TEXT NOT NULL DEFAULT '',
    service_types TEXT NOT NULL DEFAULT '[]', -- JSON array
    grievance_categories TEXT NOT NULL DEFAULT '[]', -- JSON array
    coverage_area TEXT,
    caution_notes TEXT,
    domain_hint TEXT,
    system INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'official', -- 'official' | 'official_portal' | 'demo_portal'
    status TEXT NOT NULL DEFAULT 'active',
    linked_source_ids TEXT NOT NULL DEFAULT '[]', -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_portals_scope ON portals (scope);
CREATE INDEX IF NOT EXISTS idx_portals_status ON portals (status);
CREATE INDEX IF NOT EXISTS idx_portals_kind ON portals (kind);

-- 5. Policy Comparisons (Module 2)
CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    old_document_id TEXT NOT NULL,
    new_document_id TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'processing',
    progress TEXT,
    warnings TEXT DEFAULT '[]',
    has_report INTEGER NOT NULL DEFAULT 0,
    cache_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_comparisons_cache_key ON comparisons (cache_key);
CREATE INDEX IF NOT EXISTS idx_comparisons_created ON comparisons (created_at DESC);

-- 6. Fact Verifications (Module 3)
CREATE TABLE IF NOT EXISTS verifications (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    claim_snippet TEXT NOT NULL,
    overall_verdict TEXT NOT NULL DEFAULT 'unverified',
    scope TEXT NOT NULL DEFAULT 'official',
    language TEXT NOT NULL DEFAULT 'en',
    status TEXT NOT NULL DEFAULT 'completed',
    cache_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_verifications_cache_key ON verifications (cache_key);
CREATE INDEX IF NOT EXISTS idx_verifications_created ON verifications (created_at DESC);

-- 7. Public Service Guides & Checklists (Module 4)
CREATE TABLE IF NOT EXISTS service_guides (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    query_snippet TEXT NOT NULL,
    applicant_type TEXT,
    scope TEXT NOT NULL DEFAULT 'all',
    mode TEXT NOT NULL DEFAULT 'source_backed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_guides_created ON service_guides (created_at DESC);

-- 8. Form Field Explanations (Module 4)
CREATE TABLE IF NOT EXISTS form_field_explanations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    cache_key TEXT,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_form_fields_cache_key ON form_field_explanations (cache_key);

-- 9. Civic Grievance Reports (Module 5)
CREATE TABLE IF NOT EXISTS grievances (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft',
    safety_risk INTEGER NOT NULL DEFAULT 0,
    draft_hash TEXT,
    demo_id TEXT,
    image_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_grievances_state ON grievances (state);
CREATE INDEX IF NOT EXISTS idx_grievances_category ON grievances (category);
CREATE INDEX IF NOT EXISTS idx_grievances_created ON grievances (created_at DESC);

-- 10. Browser Automation Sessions (Module 4 Extension)
CREATE TABLE IF NOT EXISTS browser_sessions (
    session_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    portal_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL DEFAULT 'demo_income_certificate',
    status TEXT NOT NULL DEFAULT 'active',
    current_step INTEGER NOT NULL DEFAULT 1,
    total_steps INTEGER NOT NULL DEFAULT 5,
    lang TEXT NOT NULL DEFAULT 'en',
    actions_count INTEGER NOT NULL DEFAULT 0,
    screenshots_count INTEGER NOT NULL DEFAULT 0,
    last_screenshot_id TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_browser_sessions_status ON browser_sessions (status);
CREATE INDEX IF NOT EXISTS idx_browser_sessions_created ON browser_sessions (created_at DESC);

-- 11. Chat Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    title TEXT NOT NULL DEFAULT 'New Conversation',
    language_setting TEXT NOT NULL DEFAULT 'auto',
    document_ids TEXT NOT NULL DEFAULT '[]', -- JSON array of attached document IDs
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations (updated_at DESC);

-- 12. Chat Messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL, -- 'user' | 'assistant'
    content TEXT NOT NULL,
    language_used TEXT,
    intent TEXT,
    grounded INTEGER,
    model TEXT,
    meta TEXT NOT NULL DEFAULT '{}', -- sources, tool_activity, verifications, checklists, grievances, browser_sessions, warnings, pending_approval
    created_at TEXT NOT NULL,
    UNIQUE (conversation_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_seq ON messages (conversation_id, seq ASC);

-- 13. Tool Runs (Safe Execution History without Arguments or Document Text)
CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    message_id TEXT,
    request_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    risk_level TEXT NOT NULL, -- 'read_only' | 'sensitive' | 'high_risk'
    status TEXT NOT NULL, -- 'success' | 'error' | 'rejected' | 'pending_approval' | 'skipped'
    duration_ms INTEGER NOT NULL DEFAULT 0,
    summary_key TEXT, -- Safe summary translation key or generic outcome (never raw inputs)
    step_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_runs_tool_name ON tool_runs (tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_runs_created ON tool_runs (created_at DESC);

-- 14. Citizen Action Approvals
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    tool_name TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    decision TEXT NOT NULL, -- 'approved' | 'denied' | 'expired'
    bound_hash TEXT,
    reference_type TEXT,
    reference_id TEXT,
    method TEXT NOT NULL DEFAULT 'ui', -- 'ui' | 'agent'
    created_at TEXT NOT NULL,
    decided_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_created ON approvals (created_at DESC);

-- 15. Activity Ledger
CREATE TABLE IF NOT EXISTS activity (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    event_type TEXT NOT NULL,
    ref_type TEXT NOT NULL,
    ref_id TEXT NOT NULL,
    severity_hint TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_created ON activity (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_event_type ON activity (event_type);
CREATE INDEX IF NOT EXISTS idx_activity_ref ON activity (ref_type, ref_id);

-- 16. Citizen Preferences
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

-- 17. Legacy Migration Ledger (for Idempotent Background Import)
CREATE TABLE IF NOT EXISTS legacy_import (
    legacy_path_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'imported'
);

-- 18. Application Metadata (Key/Value Store for System Status & Recovery)
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
