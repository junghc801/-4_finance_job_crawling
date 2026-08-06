PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS postings (
    id                  INTEGER PRIMARY KEY,
    source              TEXT NOT NULL,
    external_id         TEXT NOT NULL,
    source_url          TEXT NOT NULL,
    company             TEXT,
    title               TEXT NOT NULL,
    body_text           TEXT,
    posted_at           TEXT,
    deadline_at         TEXT,
    audience            TEXT NOT NULL DEFAULT 'unknown',
    employment_type     TEXT,
    classification_note TEXT,
    manual_audience     TEXT,
    attachments_json    TEXT NOT NULL DEFAULT '[]',
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL,
    last_changed_at     TEXT NOT NULL,
    content_hash        TEXT NOT NULL,
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_postings_posted_at ON postings(posted_at);
CREATE INDEX IF NOT EXISTS idx_postings_company ON postings(company);
CREATE INDEX IF NOT EXISTS idx_postings_audience ON postings(audience);

CREATE TABLE IF NOT EXISTS posting_snapshots (
    id           INTEGER PRIMARY KEY,
    posting_id   INTEGER NOT NULL,
    captured_at  TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    title        TEXT NOT NULL,
    body_text    TEXT,
    raw_html     TEXT,
    FOREIGN KEY (posting_id) REFERENCES postings(id),
    UNIQUE (posting_id, content_hash)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT NOT NULL,
    pages_fetched    INTEGER NOT NULL DEFAULT 0,
    postings_seen    INTEGER NOT NULL DEFAULT 0,
    postings_created INTEGER NOT NULL DEFAULT 0,
    postings_updated INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT
);

