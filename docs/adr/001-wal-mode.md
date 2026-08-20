# ADR-001: SQLite WAL Mode for Concurrent Access

## Status

Accepted

## Context

PkgForge uses SQLite (`~/.config/pkgforge/history.db`) for conversion history, backup tracking, and upstream update metadata. Multiple PkgForge instances (CLI + GUI) may run simultaneously on the same system, leading to `SQLITE_BUSY` errors under the default journal mode where writers block readers and vice versa.

## Decision

Enable WAL (Write-Ahead Logging) journal mode on every database connection:

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

**WAL benefits:**
- Readers never block writers, writers never block readers
- Concurrent reads are fully parallel
- Write transactions are serialized but non-blocking (5s busy timeout)
- The WAL file is persistent — no re-enable cost after first set

**Trade-offs:**
- Requires SQLite 3.7.0+ (Arch ships 3.40+)
- WAL file (`history.db-wal`) may persist after crash (safe, auto-recovered)
- Not suitable for NFS-mounted databases (not our use case)

## Consequences

- Multiple PkgForge instances can safely write to the same database
- The `busy_timeout` prevents immediate `SQLITE_BUSY` errors during short write bursts
- No application-level file locking needed (OS-level advisory locks via SQLite)
