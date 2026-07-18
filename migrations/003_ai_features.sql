-- AI feature foundation: scoring metadata on tasks, users table for Pro tier,
-- briefings + retrospectives caches.

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date         TIMESTAMPTZ NULL;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS duration_minutes INT NULL;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS ai_rationale     TEXT NULL;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS ai_scored        BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS last_touched_at  TIMESTAMPTZ NOT NULL DEFAULT now();

-- status gains a third value: 'someday' (parked via Weekly Triage)
-- (status is TEXT with no CHECK constraint, so no schema change needed)

CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks (due_date) WHERE due_date IS NOT NULL;

CREATE TABLE IF NOT EXISTS users (
  user_id    TEXT PRIMARY KEY,          -- Clerk user ID
  is_pro     BOOLEAN NOT NULL DEFAULT FALSE,
  pro_since  TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS briefings (
  user_id    TEXT NOT NULL,
  brief_date DATE NOT NULL,
  content    TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, brief_date)
);

CREATE TABLE IF NOT EXISTS retrospectives (
  user_id    TEXT NOT NULL,
  week_start DATE NOT NULL,
  content    TEXT NOT NULL,
  stats      JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, week_start)
);
