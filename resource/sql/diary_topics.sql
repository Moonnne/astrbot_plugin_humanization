-- name: controller_topics_select
SELECT t.id, t.day, t.topic_at, t.topic_time, t.topic, t.interact, t.reply, t.reaction,
    t.updated_at, d.coverage_gap
FROM diary_topics t
JOIN diary_days d ON t.scope=d.scope AND t.day=d.day
WHERE t.scope=?
ORDER BY t.updated_at DESC, t.id DESC
LIMIT ?;

-- name: diaries_select
SELECT id, topic_at, topic_time, topic, interact, reply, reaction, first_seq, last_seq
FROM diary_topics
WHERE scope=? AND day=?
ORDER BY updated_at DESC, id DESC;

-- name: commit_summary_insert
INSERT INTO diary_topics(scope, day, topic_at, topic_time, topic, interact, reply, reaction,
    first_seq, last_seq, created_at, updated_at) VALUES(:scope, :day, :topic_at, :topic_time,
    :topic, :interact, :reply, :reaction, :first_seq, :last_seq, :created_at, :updated_at);

-- name: commit_summary_update
UPDATE diary_topics
SET topic=COALESCE(:topic, topic),
    interact=COALESCE(:interact, interact),
    reply=COALESCE(:reply, reply),
    reaction=COALESCE(:reaction, reaction),
    updated_at=:updated_at,
    first_seq=MIN(first_seq, :first_seq),
    last_seq=MAX(last_seq, :last_seq)
WHERE id=:id AND scope=:scope AND day=:day;
