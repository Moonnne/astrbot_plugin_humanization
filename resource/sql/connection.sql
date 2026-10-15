-- name: writer
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA wal_autocheckpoint=1000;
PRAGMA journal_size_limit=4194304;

-- name: reader
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA query_only=ON;

-- name: begin_write
BEGIN IMMEDIATE;

-- name: begin_read
BEGIN;

-- name: checkpoint
PRAGMA wal_checkpoint(TRUNCATE);
