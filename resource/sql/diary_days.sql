-- name: diaries_select
SELECT * FROM diary_days d
WHERE scope=? AND (
    coverage_gap=1 OR EXISTS (
        SELECT 1 FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day
    )
)
ORDER BY day DESC LIMIT ?;

-- name: reset_targets_select
SELECT DISTINCT scope FROM diary_days
WHERE scope NOT IN (SELECT scope FROM sessions);

-- name: commit_summary_select
SELECT sealed
FROM diary_days
WHERE scope=? AND day=?;

-- name: commit_summary_update
UPDATE diary_days
SET sealed=1
WHERE scope=? AND day<?;

-- name: commit_summary_insert
INSERT INTO diary_days(scope, day, through_seq, created_at, updated_at, coverage_gap)
VALUES(?, ?, ?, ?, ?, ?)
ON CONFLICT(scope, day) DO UPDATE SET
    through_seq=excluded.through_seq,
    updated_at=excluded.updated_at,
    coverage_gap=MAX(diary_days.coverage_gap, excluded.coverage_gap);

-- name: seal_before_update
UPDATE diary_days
SET sealed=1
WHERE day<? AND sealed=0;

-- name: reset_all_delete
DELETE FROM diary_days;

-- name: info_select
SELECT day, through_seq, updated_at FROM diary_days d
WHERE scope=? AND EXISTS (
    SELECT 1 FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day
)
ORDER BY day DESC LIMIT 1;

-- name: reset_delete
DELETE FROM diary_days
WHERE scope=?;

-- name: reset_delete_2
DELETE FROM diary_days
WHERE scope=? AND day=?;
