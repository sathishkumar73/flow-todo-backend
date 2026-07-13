-- Flow Todo — initial schema
CREATE TABLE IF NOT EXISTS tasks (
  id                     SERIAL PRIMARY KEY,
  user_id                TEXT NOT NULL,                        -- Clerk user ID (e.g. user_2abc...)
  title                  TEXT NOT NULL,
  status                 TEXT NOT NULL DEFAULT 'active',       -- 'active' | 'done'
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at           TIMESTAMPTZ NULL,
  eisenhower_quadrant    TEXT NULL,                            -- 'do_first' | 'schedule' | 'delegate' | 'eliminate'
  impact_effort_quadrant TEXT NULL,                            -- 'quick_win' | 'major_project' | 'fill_in' | 'thankless'
  priority_score         INT NOT NULL DEFAULT 0,
  stack_position         BIGSERIAL
);

CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks (status);
