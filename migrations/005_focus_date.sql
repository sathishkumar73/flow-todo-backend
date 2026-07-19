-- Today's Dump: tasks explicitly flagged for today's focus
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS focus_date DATE NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_focus_date ON tasks (user_id, focus_date);
