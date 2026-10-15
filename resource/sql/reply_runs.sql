-- name: trim_delete
DELETE FROM reply_runs
WHERE id NOT IN (SELECT id FROM reply_runs ORDER BY id DESC LIMIT 1000);

-- name: start_reply_insert
INSERT INTO reply_runs(scope, started_at, trigger, status) VALUES(?, ?, ?, 'generating');

-- name: finish_reply_update
UPDATE reply_runs
SET status=?, sent_parts=?, detail=?
WHERE id=?;

-- name: reset_delete
DELETE FROM reply_runs
WHERE scope=?;

-- name: reset_all_delete
DELETE FROM reply_runs;

-- name: open_update
UPDATE reply_runs
SET status='unknown'
WHERE status='generating';
