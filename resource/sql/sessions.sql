-- name: pending_sessions_select
SELECT *
FROM sessions
WHERE last_seq>cursor;

-- name: group_sessions_select
SELECT *
FROM sessions
WHERE private=0;

-- name: session_select
SELECT *
FROM sessions
WHERE scope=?;

-- name: trim_select
SELECT scope
FROM sessions;

-- name: append_insert
INSERT INTO sessions(scope, umo, platform, self_id, group_id, private) VALUES(:scope, :umo,
    :platform, :self_id, :group_id, :private) ON CONFLICT(scope) DO NOTHING;

-- name: append_update
UPDATE sessions
SET last_seq=last_seq+1,
    human_count=human_count+?,
    last_human=CASE WHEN ? THEN ? ELSE last_human END,
    idle_waiting=CASE WHEN ? THEN 0 ELSE idle_waiting END,
    umo=CASE WHEN ? THEN ? ELSE umo END
WHERE scope=?;

-- name: commit_summary_update
UPDATE sessions
SET cursor=?, summarized_count=?
WHERE scope=?;

-- name: update_session_update
UPDATE sessions
SET cursor=CASE WHEN :set_cursor THEN :cursor ELSE cursor END,
    summarized_count=CASE WHEN :set_summarized_count THEN :summarized_count ELSE summarized_count END,
    last_human=CASE WHEN :set_last_human THEN :last_human ELSE last_human END,
    last_reply=CASE WHEN :set_last_reply THEN :last_reply ELSE last_reply END,
    next_idle=CASE WHEN :set_next_idle THEN :next_idle ELSE next_idle END,
    idle_waiting=CASE WHEN :set_idle_waiting THEN :idle_waiting ELSE idle_waiting END,
    idle_day=CASE WHEN :set_idle_day THEN :idle_day ELSE idle_day END,
    idle_count=CASE WHEN :set_idle_count THEN :idle_count ELSE idle_count END
WHERE scope=:scope;

-- name: record_reply_activity_update
UPDATE sessions
SET last_reply=?
WHERE scope=?;

-- name: reset_delete
DELETE FROM sessions
WHERE scope=?;

-- name: reset_all_delete
DELETE FROM sessions;

-- name: record_reply_activity_update_2
UPDATE sessions
SET idle_waiting=CASE WHEN last_human=? THEN 1 ELSE 0 END,
    idle_count=CASE WHEN idle_day=? THEN idle_count+1 ELSE 1 END,
    idle_day=?
WHERE scope=?;

-- name: reset_targets_select
SELECT *
FROM sessions;
