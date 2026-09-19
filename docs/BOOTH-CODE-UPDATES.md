# Booth Code Updates (admin portal)

Lets an admin see which booths are running old code and push master's code to
one lane at a time, restarting that booth's PM2 services — without SSHing in.

Portal page: **Booth Code Updates** (`/admin/booth-updates`, admin only).

---

## How it works

```
Portal  ──POST job──►  master DB (booth_deploy_jobs)
                              │
                              │ polled every 3s
                              ▼
                        mtag-deploy  (PM2 app on master)
                              │  scp bundle
                              │  ssh: purge + extract
                              │  ssh: booth_update.sh  → pip install, PM2 restart
                              ▼
                        booth (one lane)
```

The web request only writes a row. `mtag-deploy` does the work, because a single
update is an scp, a dependency install and a PM2 restart — minutes on a slow
booth, far longer than a gunicorn worker can be held.

### What "up to date" means

`mtag_backend/VERSION` — a one-line release string, shipped with the code. The
page compares master's VERSION against the one read from each booth.

**Bump `VERSION` when you cut a release.** Nothing bumps it automatically, so a
booth can report the same version while running edited code if you forget.

| Portal status | Meaning |
|---|---|
| Up to date | Booth's VERSION matches master's |
| Outdated | Booth answered with a different (or missing) VERSION |
| Unreachable | SSH failed — see the error under the badge |
| Never checked | Host configured, never successfully read |
| No booth set | Lane exists but no machine address recorded |

A booth deployed before this feature has no VERSION file, reports `unknown`, and
correctly shows as **Outdated**.

---

## One-time setup

### 1. Master

`master_bootstrap.sh` now handles all of this — re-run it, or do it by hand:

```bash
# .env on master
BOOTH_SSH_USER=iteck
BOOTH_SSH_PASSWORD=<the shared booth password>   # empty = use SSH keys

sudo apt-get install -y sshpass    # only needed when a password is set

pm2 start ecosystem.master.config.js   # now defines mtag-deploy too
pm2 save
```

Credentials live in master's `.env`, **never in the database** — a password for
49 lanes in a table the web app can read would hand anyone with database access
a shell on every booth.

Prefer SSH keys: leave `BOOTH_SSH_PASSWORD` empty and put master's public key in
each booth's `authorized_keys`. Then `sshpass` is not needed at all.

### 2. Booths

Each booth needs `VERSION` on disk, which means **one last deploy the old way**:

```bash
./deploy_booths.sh          # all booths
./deploy_booths.sh 192.168.78.61   # or just some
```

After that, updates can come from the portal.

### 3. Record each lane's address

Master's database is now the **single source of truth** for which machine runs
which lane — `deploy_booths.sh` no longer carries its own list, it asks master.

Seed it once from the addresses that used to live in that script:

```bash
scp booths.txt master:~/
ssh master 'cd mtag_backend && DJANGO_SETTINGS_MODULE=config.settings.lan \
  venv/bin/python manage.py discover_booths --from-file ~/booths.txt'
```

`discover_booths` SSHes to each address and asks the booth which lane it is —
every booth already knows, because `run_gate` reads `plaza_id` and `lane_number`
from its own `rfid_config.ini`. Nothing has to be mapped by hand.

Add `--dry-run` first to see what it would record. A booth that is unreachable,
unprovisioned, or reports a lane master does not have is **skipped and named**,
never guessed at. Re-run it any time; a booth that moved to a new IP is
re-recorded against the same lane and the move is printed.

After that, addresses are edited in the portal (pencil icon), and:

```bash
./deploy_booths.sh --list     # master's booth table
```

---

## Using it

- **Check** — reads that booth's VERSION and PM2 state. Cheap; run it any time.
- **Update** — ships master's code, reinstalls dependencies, restarts
  `mtag-web` and `mtag-gate`, then re-reads the version. **The lane is down for
  the length of the restart**, so do it when the lane is quiet.

The transcript opens automatically on an update and streams until the job ends.
Past runs are under **History**.

A lane with a job in flight refuses a second one, so a double click cannot
deploy to the same booth twice.

---

## What the update preserves

The purge before extraction keeps:

`venv` · `.env` · `rfid_config.ini` · `offline_cache.db` · `staticfiles` · `wheelhouse`

`wheelhouse` matters most. `deploy_master.sh` excludes those 34MB of booth
wheels, so master has none to ship. Booths have no route to PyPI and install
with `--no-index --find-links=wheelhouse`, so deleting a booth's wheelhouse the
way `deploy_booth.sh` does would leave `booth_update.sh` with neither wheels nor
PyPI — exit 5, with the lane's services down.

**Consequence:** a release that changes `requirements.txt` cannot be rolled out
from the portal. Use `deploy_booths.sh`, which ships a fresh wheelhouse.

---

## Failure codes

`booth_update.sh`'s exit codes are explained in the transcript:

| Code | Meaning |
|---|---|
| 2 | `.env` / `rfid_config.ini` missing, or still pointing at a local database |
| 3 | No `mtag_backend` on the booth — provision it with `deploy_booth.sh` first |
| 4 | Node/PM2 unavailable; code is in place but services were not restarted |
| 5 | Python dependencies failed (wheelhouse likely mismatched to the booth's Python) |
| 7 | Booth cannot reach master's database; nothing was started |
| 124 | Timed out (`BOOTH_DEPLOY_TIMEOUT`, default 1800s) |

---

## Where the booth list lives

```
        ┌──────────────────────────┐
        │  master: booth_machines  │  ← the only lane→address map
        └────────┬─────────────────┘
                 │
      ┌──────────┴───────────┐
      │                      │
 admin portal          deploy_booths.sh
 (edit an address)     (ssh master → manage.py list_booths)
```

`deploy_booths.sh` with no arguments asks master. Consequences worth knowing:

- **A lane with no address recorded is a booth the deploy will not reach.**
  `list_booths` names those on stderr and the script reprints them *before*
  deploying, so a gap is visible rather than silent.
- **If master is unreachable the deploy stops** rather than guessing. Naming the
  booths explicitly still works and never touches master:
  `./deploy_booths.sh 192.168.78.61 192.168.78.67`
- Master is reached as `mew02@103.7.60.67:1122` by default — override with
  `MASTER_HOST`, `MASTER_SSH_USER`, `MASTER_SSH_PORT`, `MASTER_SSH_PASSWORD`.

## Operational notes

- Every SSH runs with stdin closed (`ssh -n`). `booth_update.sh` calls `sudo` in
  a few places; with no terminal, sudo fails immediately rather than hanging the
  worker for the full timeout on a prompt nobody can answer. On a provisioned
  booth the only `sudo` is an already-satisfied `libhidapi` install.
- The bundle is copied **before** anything is deleted, so there is no window
  where a booth has neither the old code nor the new.
- The bundle is checked for `.env`, `.env.master` and `.env.booth` before it
  ships, and refuses to send if any are present.
- Two workers cannot pick up the same job (`select_for_update(skip_locked=True)`).
- Watch the worker with `pm2 logs mtag-deploy`.
