-- Junior project documents — per-project stored documents with title/slug/text/summary.
-- Reuses StoryKeep users. Apply after 002_junior_projects.sql.
--   psql "$DATABASE_URL" -f backend/migrations/003_junior_documents.sql

CREATE TABLE IF NOT EXISTS junior_documents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slug        TEXT NOT NULL,
  title       TEXT NOT NULL,
  text        TEXT NOT NULL DEFAULT '',
  summary     TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, slug)
);

CREATE INDEX IF NOT EXISTS junior_documents_user_slug_idx
  ON junior_documents (user_id, slug);
