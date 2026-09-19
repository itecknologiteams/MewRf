// PM2 process config for the m-tag backend.
// Runs two services with the project's virtualenv Python:
//   1. mtag-web   → Django app  (gunicorn, see gunicorn.conf.py)
//   2. mtag-gate  → RFID gate   (manage.py run_gate)
//
// There is no sync process. Booths are ONLINE-ONLY: booth_bootstrap.sh points
// DB_* straight at master and installs no local Postgres, so a booth has no
// database of its own to replicate. The old mtag-sync app (manage.py
// sync_service, apps/tolls/sync/) has been removed — with both ends of the
// sync being the same server it could only ever copy master onto itself.
//
// The consequence is worth stating plainly: master IS the database now. If
// master is unreachable, the lane stops. There is no local fallback.
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

// venv's own gunicorn — its shebang already points at the venv's python, so PM2
// needs no separate interpreter for it. Used for mtag-web below: `runserver` is
// Django's development server, which its own docs state has not been through
// security audits or performance testing. It was serving the booth's operator UI
// and API on 0.0.0.0:8000.
const venvGunicorn = isWin
  ? path.join(__dirname, 'venv', 'Scripts', 'gunicorn.exe')
  : path.join(__dirname, 'venv', 'bin', 'gunicorn');

// Shared options for both apps.
const common = {
  cwd: __dirname,               // always run from mtag_backend/ (where manage.py is)
  interpreter: venvPython,      // run under the venv Python
  autorestart: true,
  restart_delay: 3000,          // wait 3s before restart (avoid crash loops)
  max_restarts: 20,
  env: {
    // 'lan' — this file is for real booth deployment, where DB_* points at
    // master. 'config.settings.local' is for a developer's own machine; never
    // use it here.
    DJANGO_SETTINGS_MODULE: process.env.MTAG_SETTINGS_MODULE || 'config.settings.lan',
    PYTHONUNBUFFERED: '1',      // stream logs live to PM2
  },
};

module.exports = {
  apps: [
    {
      ...common,
      name: 'mtag-web',
      script: venvGunicorn,
      // gunicorn.conf.py carries bind/workers/threads/timeout. `interpreter`
      // is deliberately cleared: gunicorn's shebang is already the venv python,
      // and leaving `common`'s python3 in place would run it as a script.
      interpreter: 'none',
      args: '-c gunicorn.conf.py config.wsgi:application',
    },
    {
      ...common,
      name: 'mtag-gate',
      script: 'manage.py',
      args: 'run_gate',
    },
  ],
};
