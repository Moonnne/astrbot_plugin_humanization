-- name: insert
INSERT INTO message_resources(id,message_row,position,kind,name,path,size,source,created_at,status,description,mime)
SELECT ?,id,?,?,?,?,?,?,?,?,?,? FROM messages WHERE id=?;
-- name: message
SELECT * FROM messages WHERE scope=? AND direction=? AND message_id=? ORDER BY id DESC LIMIT 1;
-- name: pending
SELECT r.*,m.scope,m.umo,m.platform,m.message_id,m.group_id
FROM message_resources r JOIN messages m ON m.id=r.message_row
WHERE r.status='pending' ORDER BY m.id,r.position LIMIT 64;
-- name: for_message
SELECT * FROM message_resources WHERE message_row=? ORDER BY position;
-- name: finish
UPDATE message_resources SET description=?,status=?,provider=?,updated_at=? WHERE id=?;
-- name: render
UPDATE messages SET text=?,segments=? WHERE id=?;
-- name: by_id
SELECT * FROM messages WHERE id=?;
-- name: cleanup
SELECT path FROM resource_cleanup LIMIT 100;
-- name: cleaned
DELETE FROM resource_cleanup WHERE path=?;
-- name: waiting
SELECT COUNT(*) AS n FROM message_resources r JOIN messages m ON m.id=r.message_row
WHERE m.scope=? AND r.status='pending';
-- name: paths
SELECT path FROM message_resources WHERE path!=''
UNION SELECT path FROM resource_cleanup;
-- name: get
SELECT * FROM message_resources WHERE id=?;
-- name: stats
SELECT COUNT(*) AS resources,COALESCE(SUM(size),0) AS resource_bytes FROM message_resources;
-- name: owners
SELECT DISTINCT message_row FROM message_resources;
