// PM2 process config for the MASTER server.
//
// Runs gunicorn (production WSGI), not `manage.py runserver` — master serves
// all 10 booths' sync agents + dual-write traffic, so it needs gunicorn's
// concurrency (see gunicorn.conf.py), not the single-threaded dev server.
//
// Place this file in mtag_backend/ (next to manage.py). Then:
//   pm2 start ecosystem.master.config.js
//   pm2 save && pm2 startup
//   pm2 logs mtag-master

const path = require('path');
const isWin = process.platform === 'win32';

// venv's own gunicorn — its shebang already points at the venv's python,
// so PM2 doesn't need to be told a separate interpreter.
const venvGunicorn = isWin
  ? path.join(__dirname, 'venv', 'Scripts', 'gunicorn.exe')
  : path.join(__dirname, 'venv', 'bin', 'gunicorn');

module.exports = {
  apps: [
    {
      name: 'mtag-master',
      script: venvGunicorn,
      interpreter: 'none',
      args: '-c gunicorn.conf.py config.wsgi:application',
      cwd: __dirname,
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 20,
      env: {
        DJANGO_SETTINGS_MODULE: process.env.MTAG_SETTINGS_MODULE || 'config.settings.lan',
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
