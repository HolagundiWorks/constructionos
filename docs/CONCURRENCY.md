# Concurrency notes — Construction OS

Honest limits of the single-SQLite, stdlib design. This is a **review note**,
not a redesign. See also `AGENTS.md` §10 / §14 / §23 and the gap table row
“Concurrency / multi-user at scale”.

## What already works

- Every `db.get_conn()` sets **`PRAGMA foreign_keys=ON`**, **`journal_mode=WAL`**,
  **`synchronous=NORMAL`**, and **`busy_timeout=5000`**. A second short-lived
  connection waits instead of raising “database is locked”.
- The desktop app and the LAN/web server (`web_main.py`) can share **one**
  SQLite file on a trusted office network. WAL + busy_timeout is why that is
  tolerable for a small team.
- Writes are short-lived: open → SQL → commit → close. No long-held
  transactions across GUI callbacks.

## What does not scale (by design today)

- **One authoritative file per firm/year.** There is no multi-master sync and
  no row-level conflict merge. Two offices editing the *same* file over a flaky
  WAN will contend; prefer one server PC + LAN clients (`docs/LAN.md`).
- **No optimistic locking / version columns** on documents. Last writer wins
  for a given `id`. Acceptable for a solo/T2 contractor; not for dozens of
  concurrent field editors on one bill.
- **Roles gate the UI, not the DB.** Viewers are blocked in app code
  (`ui_guard` / API write checks); anyone with filesystem access to the `.db`
  can still open it offline.
- **Plain HTTP on the LAN.** Put an HTTPS reverse proxy in front for anything
  wider than a trusted network.

## Practical guidance

| Scenario | Recommendation |
|---|---|
| Solo / 2–3 office users on one PC or LAN | Current design — fine |
| Many field phones hitting one book | Use `/m/capture` + API; keep one server host; expect busy waits under spike |
| Separate sites that must work offline | One firm/year file per site; roll up read-only via `portfolio_store` |
| True multi-writer SaaS | Out of scope — would need a different store (not this SQLite file) |

## If contention shows up

1. Confirm only **one** writer host mounts the file (others use the LAN API).
2. Avoid copying the live `.db` while writers are active; use backup/restore
   between operations (WAL checkpoint on clean close).
3. Do **not** turn off WAL or foreign keys to “fix” locks.
4. Longer-term options (not started): per-document `updated_at` / ETag on API
   writes, or splitting hot tables — only with an explicit owner decision.

Nothing in this note changes runtime behaviour; it documents the boundary so
agents do not silently “fix” scale by inventing a second database.
