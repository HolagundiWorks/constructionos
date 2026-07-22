# Browser / LAN access

Construction OS can serve itself over your local network so colleagues open it
in a **browser** — no client to install. It's a small web server built on the
Python standard library (`http.server`), sharing the **same SQLite file** and
the same business logic as the desktop app. No web framework, no pip.

> Status: **read views + Masters data entry.** The dashboard and every register
> are viewable in the browser, and the **Masters** (sites, clients, vendors,
> materials, labour, equipment) can be added/edited/deleted there too. Billing
> then Money entry are next; the desktop app remains the full read/write client
> meanwhile.

## What you can edit (so far)

The **Masters** registers have a **+ New**, **Edit** and **Delete** in the
browser — the same fields as the desktop, built from one shared spec
(`web_masters.py`, checked against the live schema by a test so the two can't
drift):

* **Sites**, **Clients**, **Vendors**, **Materials**, **Labour**, **Equipment**,
  **Projects**, **Milestones** and the **Rate Book**.
* **Estimates** — header + line items (add/remove rows in the browser). The
  roll-up (subtotal → contingency → GST → grand total) is the same pure
  `estimate.estimate_totals` the desktop uses, and estimates never post to the
  ledger.
* **Money documents that post** — **payments, tax invoices, vendor invoices and
  running bills** (`web_docs.py`). The browser writes the document with the same
  derived amounts the desktop computes (GST, TDS, net payable, retention), then
  posts through the shared, idempotent `journal_post.post_all` — so the double
  entry comes from the desktop's `posting.py` rules, never re-implemented here.
  These are **create + view** only (records of fact), and posting is state-gated:
  a *Draft* bill saves without posting. The only money flow still desktop-only is
  the measurement-book **RA bill** workflow (Form 23/26, recoveries).

Writes are gated: a **Viewer** sees the data but no edit buttons and is refused
(403) if it POSTs anyway; only **Operator**/**Admin** may change data. Every form
carries a per-session CSRF token, and deletes that would orphan linked records
are refused with a plain message rather than a database error. Web edits are
written to the same **audit log** as the desktop (`web_create` / `web_update` /
`web_delete`). Everything else stays view-only for now.

## Starting it

**From the desktop app** — Tools › **Web / LAN access** › choose a port ›
**Start server**. It lists the exact URLs to share.

**Headless** — on an always-on office machine, with no desktop window:

```bash
cd construction_app
python web_main.py                        # 0.0.0.0:8080 (all interfaces)
python web_main.py --port 9000
python web_main.py --host 127.0.0.1       # this machine only
```

It prints, for example:

```
Open in a browser on this network:
   http://192.168.1.50:8080/
   http://127.0.0.1:8080/
```

Colleagues on the same network type that `http://<host>:<port>/` into any
browser — phone, tablet or PC.

## Which database it serves

Whatever the app is currently using:

* **installed build** → `%LOCALAPPDATA%\Construction OS\construction.db`
* **from source** → `construction.db` beside the code

If you switch company files in the desktop app, the web server follows (each
request opens the current file). SQLite is in WAL mode with a busy timeout, so
many browser clients can read at once alongside the desktop app.

## Sign-in and roles

Login is **always required** on the web — the books should never be one URL away
from anyone on the network. It reuses the desktop accounts:

* The **first visit** to a fresh database asks you to **create the administrator**.
* After that, everyone signs in with their own account.
* Roles carry over: **Admin** / **Operator** / **Viewer**. Viewers are
  read-only; the write flows (as they land) gate on Operator/Admin.

Passwords use the same versioned **PBKDF2** hashing and the same 5-try account
lockout as the desktop, and web logins are written to the audit log.

## Security — read this before exposing it

* **Plain HTTP.** Traffic (including the login) is **not encrypted**. This is
  fine on a **trusted office LAN**. Do **not** port-forward it to the internet.
  For anything wider, put it behind an HTTPS reverse proxy (nginx/Caddy) or a
  VPN — the app speaks plain HTTP on localhost behind it.
* **The `users` table is never served** — password hashes are excluded from the
  browsable registers, as is app configuration.
* CSRF is guarded on the login form (double-submit token); session cookies are
  `HttpOnly` + `SameSite=Lax`. A POST body is capped at 2 MB.
* Only start the server when you want it reachable; **Stop** unbinds the port.

## What's under the hood

| Module | Role |
|---|---|
| `webserver.py` | `ThreadingHTTPServer` plumbing + `WebServer` start/stop lifecycle |
| `webapp.py` | routing, sessions, the login gate, the read views (`handle(request) → response`, socket-free and unit-tested) |
| `webrender.py` | HTML + CSS (HCW look, theme-aware, responsive), standard-library escaping |
| `netinfo.py` | works out the LAN URLs to share |
| `web_main.py` | headless entry point (`--host` / `--port`) |

Because `webapp.handle` is just `Request → Response`, the whole app is testable
without a socket — see `tests/test_web.py`.
