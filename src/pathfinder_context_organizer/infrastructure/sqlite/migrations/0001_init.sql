CREATE TABLE projects (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE source_sessions (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    source_type TEXT NOT NULL,
    session_identity TEXT NOT NULL,
    masked_source_ref TEXT NOT NULL,
    source_status TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_checked_at TEXT NOT NULL
);

CREATE TABLE topics (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE import_runs (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    source_session_id TEXT NOT NULL REFERENCES source_sessions(id) ON DELETE RESTRICT,
    triggered_by TEXT NOT NULL,
    consent_granted_at TEXT,
    provider_adapter TEXT,
    model_name TEXT,
    redacted_scope_hash TEXT NOT NULL,
    event_range TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_code TEXT,
    source_fingerprint_before TEXT NOT NULL,
    source_fingerprint_after TEXT,
    source_size_bytes INTEGER NOT NULL,
    source_last_modified_at TEXT NOT NULL,
    interrupted_reason TEXT
);

CREATE TABLE context_items (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    import_run_id TEXT NOT NULL REFERENCES import_runs(id) ON DELETE RESTRICT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    content_summary TEXT NOT NULL,
    review_status TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    quality_signals_json TEXT NOT NULL,
    source_range TEXT NOT NULL,
    evidence_summary TEXT NOT NULL,
    masked_source_ref_snapshot TEXT NOT NULL,
    supersedes_context_item_id TEXT REFERENCES context_items(id) ON DELETE RESTRICT,
    user_modified INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    CHECK(user_modified IN (0,1)),
    CHECK(supersedes_context_item_id <> id)
);

CREATE TABLE context_item_topics (
    context_item_id TEXT NOT NULL REFERENCES context_items(id) ON DELETE RESTRICT,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
    PRIMARY KEY(context_item_id, topic_id)
);

CREATE TABLE handoff_packages (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    topic_id TEXT REFERENCES topics(id) ON DELETE RESTRICT,
    purpose TEXT NOT NULL,
    scope_summary TEXT NOT NULL,
    token_budget_applied INTEGER NOT NULL,
    template_version TEXT NOT NULL,
    project_name_snapshot TEXT NOT NULL,
    topic_name_snapshot TEXT,
    approved_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(token_budget_applied IN (0,1))
);

CREATE TABLE handoff_package_items (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    handoff_package_id TEXT NOT NULL REFERENCES handoff_packages(id) ON DELETE RESTRICT,
    context_item_id TEXT NOT NULL REFERENCES context_items(id) ON DELETE RESTRICT,
    disposition TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    exclusion_reason TEXT,
    masking_applied INTEGER NOT NULL,
    render_tier TEXT,
    UNIQUE(handoff_package_id, context_item_id),
    CHECK(sequence >= 0),
    CHECK(masking_applied IN (0,1)),
    CHECK((disposition = 'explicitly_excluded' AND render_tier IS NULL) OR (disposition = 'included' AND render_tier IS NOT NULL AND render_tier IN ('essential','standard','detail')))
);

CREATE TABLE handoff_renders (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    handoff_package_id TEXT NOT NULL REFERENCES handoff_packages(id) ON DELETE RESTRICT,
    profile TEXT NOT NULL,
    template_version TEXT NOT NULL,
    token_budget INTEGER,
    token_count INTEGER,
    token_count_kind TEXT,
    tokenizer_ref TEXT,
    status TEXT NOT NULL,
    generated_at TEXT,
    masked_output_ref TEXT,
    error_code TEXT,
    CHECK(token_budget >= 0),
    CHECK(token_count >= 0)
);

CREATE TABLE audit_events (
    id TEXT NOT NULL PRIMARY KEY CHECK(id <> ''),
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL,
    result_status TEXT NOT NULL,
    reason_code TEXT
);

CREATE TABLE context_item_source_events (
    context_item_id TEXT NOT NULL REFERENCES context_items(id) ON DELETE RESTRICT,
    source_event_id TEXT NOT NULL,
    ord INTEGER NOT NULL CHECK(ord >= 0),
    PRIMARY KEY(context_item_id, source_event_id),
    UNIQUE(context_item_id, ord)
);

CREATE INDEX idx_source_sessions_project_id ON source_sessions(project_id);

CREATE INDEX idx_source_sessions_source_status ON source_sessions(source_status);

CREATE INDEX idx_topics_project_id ON topics(project_id);

CREATE INDEX idx_import_runs_source_session_id ON import_runs(source_session_id);

CREATE INDEX idx_import_runs_status ON import_runs(status);

CREATE INDEX idx_import_runs_started_at ON import_runs(started_at);

CREATE INDEX idx_context_items_import_run_id ON context_items(import_run_id);

CREATE INDEX idx_context_items_type ON context_items(type);

CREATE INDEX idx_context_items_sensitivity ON context_items(sensitivity);

CREATE INDEX idx_context_items_created_at ON context_items(created_at);

CREATE INDEX idx_context_items_updated_at ON context_items(updated_at);

CREATE INDEX idx_handoff_packages_project_id ON handoff_packages(project_id);

CREATE INDEX idx_handoff_packages_topic_id ON handoff_packages(topic_id);

CREATE INDEX idx_handoff_package_items_package_id ON handoff_package_items(handoff_package_id);

CREATE INDEX idx_handoff_package_items_context_item_id ON handoff_package_items(context_item_id);

CREATE INDEX idx_handoff_renders_package_id ON handoff_renders(handoff_package_id);

CREATE INDEX idx_audit_events_occurred_at ON audit_events(occurred_at);

CREATE INDEX idx_context_items_review_lifecycle ON context_items(review_status, lifecycle_status);

CREATE INDEX idx_cise_context_item ON context_item_source_events(context_item_id);

CREATE INDEX idx_cise_ord ON context_item_source_events(ord);

CREATE INDEX idx_cise_source_event ON context_item_source_events(source_event_id);

CREATE INDEX idx_context_item_topics_context_item ON context_item_topics(context_item_id);

CREATE INDEX idx_context_item_topics_topic ON context_item_topics(topic_id);

CREATE INDEX idx_audit_events_entity ON audit_events(entity_type, entity_id);

CREATE UNIQUE INDEX idx_reviewable_fingerprint ON import_runs(source_session_id, source_fingerprint_before) WHERE status IN ('awaiting_review', 'completed');
