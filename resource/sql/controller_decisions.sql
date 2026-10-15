-- name: decisions_select
SELECT *
FROM controller_decisions
WHERE scope=?
ORDER BY id DESC
LIMIT 10;

-- name: record_decision_insert
INSERT INTO controller_decisions(scope, created_at, observed_through_seq, last_human_at, trigger,
    reply_required, decision_json, outcome) VALUES(?, ?, ?, ?, ?, ?, ?, ?);

-- name: record_decision_delete
DELETE FROM controller_decisions
WHERE scope=? AND id NOT IN (
    SELECT id FROM controller_decisions WHERE scope=? ORDER BY id DESC LIMIT 10
);

-- name: finish_decision_update
UPDATE controller_decisions
SET outcome=?
WHERE id=?;

-- name: reset_delete
DELETE FROM controller_decisions
WHERE scope=?;

-- name: reset_all_delete
DELETE FROM controller_decisions;

-- name: open_update
UPDATE controller_decisions
SET outcome='unconfirmed'
WHERE outcome='pending';
