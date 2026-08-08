// PM2 process config for the m-tag backend.
// Runs three services with the project's virtualenv Python:
//   1. mtag-web   → Django server   (manage.py runserver)
//   2. mtag-gate  → RFID gate       (manage.py run_gate)   — local DB only
//   3. mtag-sync  → master sync     (manage.py sync_service) — the ONLY process
//                                     that talks to master
//
// mtag-gate and mtag-sync are separate on purpose. The gate reads and writes
// only its local database and holds no replication logic, so if master is
// unreachable the sync process backs off and retries while the lane keeps
// running. mtag-sync's behaviour is driven by GATE_MODE in .env (entry|exit).
//
// Place this file in mtag_backend/ (next to manage.py). Then:
//   pm2 start ecosystem.config.js
//   pm2 save && pm2 startup        # run on boot
//   pm2 logs mtag-gate             # watch gate scans
//
// Prereqs on the machine:
//   - venv created + requirements installed (venv/bin/python3 or venv/Scripts/python.exe)
//   - rfid_config.ini present next to manage.py (run_gate reads it)
//   - com.rfid SDK importable in the venv (for run_gate)

const path = require('path');
const isWin = process.platform === 'win32';

// venv interpreter — picked automatically for the OS.
const venvPython = isWin
  ? path.join(__dirname, 'venv', 'Scripts', 'python.exe')
  : path.join(__dirname, 'venv', 'bin', 'python3');

// Shared options for both apps.
const common = {
  cwd: __dirname,               // always run from mtag_backend/ (where manage.py is)
  interpreter: venvPython,      // run under the venv Python
  autorestart: true,
  restart_delay: 3000,          // wait 3s before restart (avoid crash loops)
  max_restarts: 20,
  env: {
    // 'lan' — this file is for real booth deployment, where the sync agent
    // (local <-> master Postgres) and online-only dual-write MUST be on.
    // 'config.settings.local' disables the sync agent entirely — only use
    // that by hand for a developer's own machine, never here.
    DJANGO_SETTINGS_MODULE: process.env.MTAG_SETTINGS_MODULE || 'config.settings.lan',
    PYTHONUNBUFFERED: '1',      // stream logs live to PM2
  },
};

module.exports = {
  apps: [
    {
      ...common,
      name: 'mtag-web',
      script: 'manage.py',
      // --noreload: Django's auto-reloader forks a child, which confuses PM2.
      args: 'runserver 0.0.0.0:8000 --noreload',
    },
    {
      ...common,
      name: 'mtag-gate',
      script: 'manage.py',
      args: 'run_gate',
    },
    {
      ...common,
      name: 'mtag-sync',
      script: 'manage.py',
      // Mode comes from GATE_MODE in .env — do NOT hardcode --mode here, or a
      // booth's .env and its sync behaviour can silently disagree.
      args: 'sync_service',
    },
  ],
};
