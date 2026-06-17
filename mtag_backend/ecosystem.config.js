// PM2 process config for the m-tag backend.
// Runs two services with the project's virtualenv Python:
//   1. mtag-web   → Django server  (manage.py runserver)
//   2. mtag-gate  → RFID gate      (manage.py run_gate)
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
    DJANGO_SETTINGS_MODULE: 'config.settings.local',  // dev/test (sync OFF). Use 'config.settings.lan' for prod.
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
      name: 'etag-gate',
      script: 'manage.py',
      args: 'run_gate',
    },
  ],
};
