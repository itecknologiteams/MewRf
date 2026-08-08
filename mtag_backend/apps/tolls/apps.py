import os
import threading
from django.apps import AppConfig


class TollsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tolls'
    label = 'tolls'

    def ready(self):
        import sys
        from django.conf import settings

        # The master sync agent is NO LONGER started here. It runs as its own
        # process — `manage.py sync_service`, PM2 app `mtag-sync` — so that the
        # web app and the gate hold no replication logic and never block on
        # master. Starting it here also meant every `manage.py <anything>`
        # (shell, migrate, showmigrations) silently spun up a sync thread.
        #
        # Gates the ANPR gate auto-start ONLY. Syncing is not affected by any
        # setting — it runs iff the mtag-sync process is running.
        if not getattr(settings, 'ANPR_GATE_ENABLED',
                       getattr(settings, 'SYNC_AGENT_ENABLED', True)):
            return

        # Under Django's dev-server reloader the monitor process runs first
        # with RUN_MAIN unset — skip it to avoid double-starting threads.
        # Under gunicorn/uwsgi there is no reloader, so RUN_MAIN is never set;
        # we detect that by checking whether 'runserver' is in sys.argv.
        is_runserver = 'runserver' in sys.argv
        if is_runserver and os.environ.get('RUN_MAIN') != 'true':
            return

        # Start ANPR gate if config exists next to manage.py
        base_dir = os.path.dirname(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'manage.py')
            )
        )
        cfg_path = os.path.join(base_dir, 'anpr_config.ini')
        if os.path.exists(cfg_path):
            threading.Thread(
                target=self._start_anpr_gate,
                args=(cfg_path,),
                name='anpr-gate',
                daemon=True,
            ).start()

    def _start_anpr_gate(self, cfg_path: str):
        import configparser
        import logging
        log = logging.getLogger('apps.tolls.anpr_gate')

        try:
            from apps.tolls.management.commands.run_gate import resolve_plaza_lane
            from apps.tolls.management.commands.run_anpr_gate import AnprGateController
        except Exception as exc:
            log.error("[anpr] Import error: %s", exc)
            return

        cfg = configparser.ConfigParser()
        cfg.read(cfg_path)

        gate_mode    = cfg.get('gate', 'mode',          fallback='entry').strip().lower()
        plaza_id     = cfg.get('gate', 'plaza_id',      fallback='').strip()
        plaza_uuid   = cfg.get('gate', 'plaza_uuid',    fallback='').strip()
        lane_id      = cfg.get('gate', 'lane_id',       fallback='').strip() or None
        lane_number  = cfg.get('gate', 'lane_number',   fallback='').strip() or None
        plate_cooldown = float(cfg.get('gate', 'plate_cooldown', fallback='5.0'))
        ws_url       = cfg.get('anpr', 'ws_url',        fallback='ws://localhost:3003')
        serial_port  = cfg.get('barrier', 'port',       fallback='/dev/ttyUSB0')
        serial_baud  = int(cfg.get('barrier', 'baudrate', fallback='115200'))
        open_secs    = float(cfg.get('barrier', 'open_seconds', fallback='2.0'))
        display_ip   = cfg.get('display', 'display_ip', fallback='192.168.78.12')

        try:
            plaza_uuid, lane_id = resolve_plaza_lane(plaza_id, plaza_uuid, lane_number, lane_id)
        except Exception as exc:
            log.error("[anpr] Plaza/lane config error: %s", exc)
            return

        class _Stdout:
            def write(self, msg):
                log.info(msg.strip())

        gate = AnprGateController(
            gate_mode=gate_mode,
            plaza_id=plaza_uuid,
            lane_id=lane_id,
            serial_port=serial_port,
            serial_baud=serial_baud,
            open_secs=open_secs,
            display_ip=display_ip,
            tag_cooldown=plate_cooldown,
            stdout=_Stdout(),
        )

        log.info("[anpr] Gate thread started — connecting to %s", ws_url)
        gate.run_ws(ws_url)
