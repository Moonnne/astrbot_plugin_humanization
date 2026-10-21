-- name: sessions
SELECT scope FROM sessions UNION SELECT scope FROM diary_days
UNION SELECT scope FROM controller_decisions ORDER BY scope;

-- name: stats
SELECT
 (SELECT COUNT(*) FROM sessions WHERE :scope='' OR scope IN (SELECT value FROM json_each(:scopes))) AS sessions,
 (SELECT COUNT(*) FROM messages WHERE :scope='' OR scope IN (SELECT value FROM json_each(:scopes))) AS messages,
 (SELECT COUNT(*) FROM diary_topics WHERE :scope='' OR scope IN (SELECT value FROM json_each(:scopes))) AS topics,
 (SELECT COUNT(*) FROM diary_days WHERE :scope='' OR scope IN (SELECT value FROM json_each(:scopes))) AS diaries,
 (SELECT COUNT(*) FROM controller_decisions WHERE :scope='' OR scope IN (SELECT value FROM json_each(:scopes))) AS decisions,
 (SELECT COUNT(*) FROM controller_decisions WHERE (:scope='' OR scope IN (SELECT value FROM json_each(:scopes)))
   AND json_extract(decision_json,'$.reply')=1) AS planned_replies,
 (SELECT COUNT(*) FROM controller_decisions WHERE (:scope='' OR scope IN (SELECT value FROM json_each(:scopes)))
   AND outcome='processed') AS processed;

-- name: messages
SELECT *, sent_at AS timestamp, text AS headline, direction AS kind,
 sender_name || ' ' || sender_id || ' ' || message_id || ' ' || text AS search
FROM messages

-- name: decisions
SELECT *, created_at AS timestamp, observed_through_seq AS seq,
 date(created_at,'unixepoch',:offset) AS day, outcome AS kind,
 json_extract(decision_json,'$.reason') AS headline, decision_json AS search
FROM controller_decisions

-- name: topics
SELECT *, topic_at AS timestamp, first_seq AS seq, topic AS headline,
 '' AS kind, topic || ' ' || interact || ' ' || reply || ' ' || reaction AS search
FROM diary_topics

-- name: diaries
SELECT d.*, d.day AS id, d.updated_at AS timestamp, d.through_seq AS seq,
 d.day AS headline, CAST(d.sealed AS TEXT) AS kind,
 COALESCE((SELECT group_concat(topic || ' ' || interact || ' ' || reply || ' ' || reaction,' ')
 FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day),'') AS search,
 (SELECT COUNT(*) FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day) AS topic_count
FROM diary_days d

-- name: count
SELECT COUNT(*) AS total FROM ({source})
WHERE (:sessions='[]' OR (
 json_extract(scope,'$[0]') || ':' || CASE json_extract(scope,'$[2]')
 WHEN 'private' THEN 'FriendMessage' ELSE 'GroupMessage' END || ':' || json_extract(scope,'$[3]')
 IN (SELECT value FROM json_each(:sessions))))
 AND (:chat_type='' OR json_extract(scope,'$[2]')=:chat_type)
 AND (:start='' OR day>=:start) AND (:end='' OR day<=:end)
 AND (:q='' OR instr(lower(search),lower(:q))>0)
 AND ({filters})

-- name: page
SELECT * FROM ({source})
WHERE (:sessions='[]' OR (
 json_extract(scope,'$[0]') || ':' || CASE json_extract(scope,'$[2]')
 WHEN 'private' THEN 'FriendMessage' ELSE 'GroupMessage' END || ':' || json_extract(scope,'$[3]')
 IN (SELECT value FROM json_each(:sessions))))
 AND (:chat_type='' OR json_extract(scope,'$[2]')=:chat_type)
 AND (:start='' OR day>=:start) AND (:end='' OR day<=:end)
 AND (:q='' OR instr(lower(search),lower(:q))>0)
 AND ({filters})
ORDER BY {order}, scope, id LIMIT :limit OFFSET :skip

-- name: sort_conversation
COALESCE((SELECT NULLIF(value,key) FROM json_each(:session_labels) WHERE key=
 json_extract(scope,'$[0]') || ':' || CASE json_extract(scope,'$[2]')
 WHEN 'private' THEN 'FriendMessage' ELSE 'GroupMessage' END || ':' || json_extract(scope,'$[3]')),
 json_extract(scope,'$[3]')) COLLATE NOCASE

-- name: sort_state_messages
sender_name COLLATE NOCASE

-- name: sort_state_decisions
outcome COLLATE NOCASE

-- name: sort_state_topics
day

-- name: sort_state_diaries
sealed

-- name: filter_messages
(:kind='' OR direction=:kind)
 AND (:sender='' OR instr(lower(sender_name || ' ' || sender_id),lower(:sender))>0)
 AND (:component='' OR EXISTS (SELECT 1 FROM json_each(segments)
   WHERE json_extract(value,'$.type')=:component))

-- name: filter_decisions
(:kind='' OR outcome=:kind)
 AND (:reply='' OR CAST(json_extract(decision_json,'$.reply') AS TEXT)=:reply)
 AND (:emotion='' OR json_extract(decision_json,'$.emotion.primary')=:emotion)
 AND (:required='' OR CAST(reply_required AS TEXT)=:required)
 AND (:trigger='' OR trigger=:trigger)

-- name: filter_topics
(:participant='' OR instr(lower(interact),lower(:participant))>0)
 AND (:bot_reply='' OR instr(lower(reply),lower(:bot_reply))>0)

-- name: filter_diaries
(:kind='' OR CAST(sealed AS TEXT)=:kind)
 AND (:coverage_gap='' OR CAST(coverage_gap AS TEXT)=:coverage_gap)

-- name: diary_topics
SELECT * FROM diary_topics WHERE scope=? AND day=? ORDER BY topic_at,id;

-- name: delete_messages
DELETE FROM messages WHERE scope=? AND id=?;

-- name: delete_decisions
DELETE FROM controller_decisions WHERE scope=? AND id=?;

-- name: delete_topics
DELETE FROM diary_topics WHERE scope=? AND id=?;

-- name: delete_diaries
DELETE FROM diary_days WHERE scope=? AND day=?;
