-- name: recent_select
SELECT *
FROM messages
WHERE scope=?
ORDER BY seq DESC
LIMIT ?;

-- name: message_count_select
SELECT COUNT(*) AS count
FROM messages
WHERE scope=? AND (? IS NULL OR seq<=?);

-- name: pending_messages_select
SELECT *
FROM messages
WHERE scope=? AND seq>?
ORDER BY seq
LIMIT ?;

-- name: preceding_messages_select
SELECT *
FROM messages
WHERE scope=? AND seq<=?
ORDER BY seq DESC
LIMIT ?;

-- name: append_insert
INSERT INTO messages(scope, umo, platform, self_id, group_id, sender_id, sender_name, message_id,
    sent_at, received_at, text, segments, private, day, direction, seq, human_count) VALUES(:scope,
    :umo, :platform, :self_id, :group_id, :sender_id, :sender_name, :message_id, :sent_at,
    :received_at, :text, :segments, :private, :day, :direction, :seq, :human_count);

-- name: append_delete
DELETE FROM messages
WHERE scope=? AND seq<=?;

-- name: reset_delete
DELETE FROM messages
WHERE scope=?;

-- name: reset_all_delete
DELETE FROM messages;

-- name: info_select
SELECT
    (SELECT COUNT(*) FROM messages WHERE scope=?) AS message_count,
    (SELECT COUNT(DISTINCT day) FROM diary_topics WHERE scope=?) AS diary_count,
    COALESCE(
        (SELECT human_count-summarized_count FROM sessions WHERE scope=?), 0
    ) AS pending_count;

-- name: trim_delete
DELETE FROM messages
WHERE scope=? AND id NOT IN (
    SELECT id FROM messages WHERE scope=? ORDER BY seq DESC LIMIT ?
);

-- name: append_select
SELECT id
FROM messages
WHERE scope=? AND direction=? AND message_id=?;
