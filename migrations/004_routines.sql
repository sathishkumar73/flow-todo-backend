-- Flow Todo — routine tasks (recurring habits / daily checklist)
CREATE TABLE IF NOT EXISTS routines (
  id             SERIAL PRIMARY KEY,
  user_id        TEXT NOT NULL,
  title          TEXT NOT NULL,
  frequency      TEXT NOT NULL DEFAULT 'daily'
                   CHECK (frequency IN ('daily', 'weekdays', 'weekly', 'monthly')),
  day_of_week    INTEGER NULL,   -- 0=Sun…6=Sat; used when frequency='weekly'
  day_of_month   INTEGER NULL,   -- 1-31; used when frequency='monthly'
  last_done_at   TIMESTAMPTZ NULL,
  is_active      BOOLEAN NOT NULL DEFAULT true,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_routines_user_id ON routines (user_id);
