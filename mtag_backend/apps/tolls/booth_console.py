"""The booth console — one page, served by the booth, showing what the lane is doing.

Reachable at http://<booth-lan-ip>:8000/booth/ . It is served BY the booth rather
than by master on purpose:

  * the things it reports on — rfid_config.ini, /dev/ttyUSB0, the barrier service
    on 127.0.0.1:3005, the reader on the booth's own subnet — are only visible
    from the booth itself;
  * same-origin means no CORS to widen on 21 machines and no second address to
    keep in step with a re-imaged booth; and
  * it ships with the code that booth_update.sh already deploys, so there is
    nothing extra to install.

Authentication is the portal's: the booth's Django talks to master's database, so
an operator logs in here with the same credentials. Reads need an operator;
anything that changes the lane — writing config, restarting the gate, raising the
boom — needs an admin, because each of those can stop a lane taking money.

The page itself is public. It is static markup with no booth data in it, and
every panel is filled by an authenticated call; serving it anonymously is what
lets it render its own login form instead of a Django 403 page.
"""

import logging
import os
import time

from django.http import HttpResponse
from django.shortcuts import render
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.users.permissions import IsAdmin, IsOperator
from utils.code_version import get_code_version
from utils.response import error_response, success_response

from . import booth_activity, booth_probe
from .models import PendingGateOpen, Plaza, TollLane

logger = logging.getLogger(__name__)


class BoothConsoleThrottle(UserRateThrottle):
    """A rate that a live console can actually live within.

    The page polls: detections every 2s, the overview and barrier log every 5s.
    That is roughly 3,000 requests an hour from one open tab, against a default
    `user` rate of 2,000 — so the console would throttle itself into a stalled
    page after twenty minutes. It keeps a ceiling rather than dropping throttling
    altogether: a runaway tab, or one left open over a weekend, should still stop
    well before it becomes the reason a lane is slow.

    `rate` is set here rather than as a scope in DEFAULT_THROTTLE_RATES because
    SimpleRateThrottle only consults settings when the class has no rate of its
    own — and a scope missing from settings raises ImproperlyConfigured on every
    request, which is a 500 on the diagnostics page someone opened precisely
    because something was already wrong. Carrying the value here means the
    console cannot be broken by a settings file that has not been redeployed.
    """
    scope = 'booth_console'
    rate = '20000/hour'


class BoothReadView(APIView):
    permission_classes = [IsOperator]
    throttle_classes = [BoothConsoleThrottle]


class BoothWriteView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [BoothConsoleThrottle]


# ── The page ─────────────────────────────────────────────────────────────────

def booth_console_page(request):
    """Serve the console shell. No booth data — every panel fetches its own."""
    return render(request, 'booth_console.html', {
        'code_version': get_code_version(),
        'is_booth': booth_probe.is_booth(),
    })


# ── Overview: identity, config summary, and every fast probe ────────────────

class BoothOverviewView(BoothReadView):
    """Everything the header and the health tiles need, in one round trip.

    Deliberately one endpoint rather than six: the page polls this every few
    seconds, and six polls would be six authentications, six DB touches and six
    chances for a panel to disagree with its neighbour about what time it is.

    The camera is NOT probed here — opening an RTSP stream takes seconds even
    when the camera is healthy, and it would make this the slowest thing on the
    page. It has its own endpoint.
    """

    def get(self, request):
        if not booth_probe.is_booth():
            return success_response(data={
                'is_booth': False,
                'message': (
                    f'{booth_probe.CONFIG_FILENAME} was not found beside manage.py, '
                    f'so this host is not a booth. The console runs on the booth '
                    f'PC itself — open http://<booth-lan-ip>:8000/booth/.'
                ),
                'code_version': get_code_version(),
                'server_time': time.time(),
            })

        parser = booth_probe.raw_config_parser()
        identity = booth_probe.gate_identity(parser)

        reader = booth_probe.probe_tcp(identity['reader_host'], identity['reader_port'])
        barrier_service = booth_probe.probe_barrier_service(identity['barrier_service_url'])
        serial = booth_probe.probe_serial(identity['barrier_port'])
        display = booth_probe.probe_http(
            f"http://{identity['display_ip']}/" if identity['display_ip'] else '')
        database = booth_probe.probe_database()
        pm2 = booth_probe.pm2_status()

        # Which route the boom is actually on. BarrierBackend picks the service
        # when it answers AND its own port is open, unless 'serial' is pinned —
        # mirror that here so the console reports the live route rather than the
        # configured preference.
        if identity['barrier_mode'] == 'serial':
            barrier_route = 'serial'
        elif barrier_service.get('usable'):
            barrier_route = 'service'
        else:
            barrier_route = 'serial'

        return success_response(data={
            'is_booth': True,
            'code_version': get_code_version(),
            'server_time': time.time(),
            'identity': identity,
            'plaza': self._plaza(identity, database['ok']),
            'health': {
                'reader': reader,
                'barrier_service': barrier_service,
                'barrier_serial': serial,
                'barrier_route': barrier_route,
                'display': display,
                'database': database,
                'pm2': pm2,
            },
            'recorder': self._recorder_stats(),
            'activity': booth_activity.read_summary(),
        })

    def _plaza(self, identity, db_ok):
        """Resolve the configured plaza/lane to their database rows.

        A booth whose plaza_id is not in the database is a booth whose gate
        refuses to start (resolve_plaza_lane raises), so this doubles as the
        check for the single most common misconfiguration.
        """
        result = {'resolved': False, 'name': '', 'lane_id': None,
                  'plaza_row_id': None, 'error': ''}
        if not db_ok:
            result['error'] = 'master unreachable — cannot resolve'
            return result
        raw = (identity.get('plaza_id') or '').strip()
        if not raw:
            result['error'] = 'plaza_id is not set in [gate]'
            return result
        try:
            number = int(raw)
        except ValueError:
            result['error'] = f"plaza_id '{raw}' is not an integer"
            return result
        try:
            plaza = Plaza.objects.get(plaza_id=number)
        except Plaza.DoesNotExist:
            result['error'] = f'no plaza with plaza_id {number} exists on master'
            return result
        except Exception as exc:
            result['error'] = str(exc).strip().splitlines()[0]
            return result

        result.update({'resolved': True, 'name': plaza.name,
                       'display_id': plaza.display_id, 'plaza_row_id': plaza.id,
                       'is_active': plaza.is_active})
        lane_number = (identity.get('lane_number') or '').strip()
        if lane_number:
            try:
                lane = TollLane.objects.get(
                    plaza_id=plaza.id, lane_number=int(lane_number))
                result['lane_id'] = lane.id
                result['lane_active'] = lane.is_active
            except (TollLane.DoesNotExist, ValueError):
                result['error'] = (
                    f'lane {lane_number} does not exist at plaza {number} — '
                    f'the gate will refuse to start'
                )
            except Exception as exc:
                result['error'] = str(exc).strip().splitlines()[0]
        return result

    def _recorder_stats(self):
        """How the local activity file is doing, without starting a writer.

        `get_recorder()` would spin up a writer thread inside gunicorn on a host
        that has no gate, so the module global is read directly and an absent
        recorder is reported as what it is.
        """
        recorder = getattr(booth_activity, '_recorder', None)
        if recorder is None:
            path = booth_activity.get_db_path()
            return {
                'in_process': False,
                'db_path': path,
                'db_exists': os.path.exists(path),
                'db_size_bytes': os.path.getsize(path) if os.path.exists(path) else 0,
            }
        stats = recorder.stats()
        stats['in_process'] = True
        return stats


# ── rfid_config.ini ──────────────────────────────────────────────────────────

class BoothConfigView(BoothReadView):
    """GET the booth's config; POST changes to the keys the console may set."""

    def get(self, request):
        config = booth_probe.read_config()
        config['editable'] = {
            section: sorted(keys) for section, keys in booth_probe.EDITABLE.items()
        }
        config['identity'] = (
            booth_probe.gate_identity() if config['exists'] else {}
        )
        return success_response(data=config)

    def post(self, request):
        # Writing is an admin action — a bad threshold takes the lane down.
        if not IsAdmin().has_permission(request, self):
            return error_response(
                'Changing booth configuration requires an admin account.',
                status_code=403)
        if not booth_probe.is_booth():
            return error_response(
                f'{booth_probe.CONFIG_FILENAME} not found — this host is not a booth.',
                status_code=404)

        raw_changes = request.data.get('changes')
        if not isinstance(raw_changes, dict) or not raw_changes:
            return error_response(
                "Send {'changes': {'scanner.rssi_detect': '-70', ...}}.")

        changes = {}
        malformed = []
        for dotted, value in raw_changes.items():
            section, _, key = str(dotted).partition('.')
            if not section or not key:
                malformed.append(dotted)
                continue
            changes[(section.strip().lower(), key.strip().lower())] = value
        if malformed:
            return error_response(
                f"Keys must be 'section.key': {', '.join(sorted(malformed))}")

        current = booth_probe.current_values()
        errors = booth_probe.validate_changes(changes, current)
        if errors:
            # 422, not 400: the request was well-formed and was refused on its
            # content. The console shows these verbatim — they are the same
            # sentences run_gate would print if it were allowed to start.
            return error_response(
                'These values would stop the gate from starting.',
                errors={'validation': errors}, status_code=422)

        # Nothing to do is worth saying out loud rather than leaving a .bak and
        # restarting a lane for no reason.
        unchanged = {
            f'{s}.{k}': v for (s, k), v in changes.items()
            if str(v).strip() == str(current.get(f'{s}.{k}', '')).strip()
        }
        if len(unchanged) == len(changes):
            return success_response(
                data={'applied': {}, 'restarted': False, 'unchanged': unchanged},
                message='No values differ from what is already configured.')

        if request.data.get('dry_run'):
            return success_response(
                data={'would_apply': {f'{s}.{k}': v for (s, k), v in changes.items()},
                      'unchanged': unchanged, 'restarted': False},
                message='Validated. Nothing written — dry_run was set.')

        try:
            written = booth_probe.write_changes(changes)
        except Exception as exc:
            logger.exception('[booth] Config write failed')
            return error_response(f'Could not write the config: {exc}',
                                  status_code=500)

        logger.warning(
            '[booth] %s changed rfid_config.ini: %s',
            getattr(request.user, 'phone', request.user), written['applied'],
        )

        result = {'applied': written['applied'], 'backup': written['backup'],
                  'unchanged': unchanged, 'restarted': False, 'restart': None}
        message = 'Written. The gate reads this file at startup — restart it to apply.'

        if request.data.get('restart'):
            restart = booth_probe.pm2_restart('mtag-gate')
            result['restarted'] = restart.get('ok', False)
            result['restart'] = restart
            message = (
                'Written and mtag-gate restarted.' if restart.get('ok')
                else f"Written, but the restart failed: {restart.get('error') or restart.get('output')}"
            )
        return success_response(data=result, message=message)


class BoothConfigRestoreView(BoothWriteView):
    """Put back the .bak the last write left, and optionally restart the gate."""

    def post(self, request):
        if not booth_probe.restore_backup():
            return error_response(
                'There is no rfid_config.ini.bak to restore from.', status_code=404)
        logger.warning('[booth] %s restored rfid_config.ini from backup',
                       getattr(request.user, 'phone', request.user))
        result = {'restored': True, 'restarted': False}
        message = 'Restored from backup. Restart the gate to apply it.'
        if request.data.get('restart'):
            restart = booth_probe.pm2_restart('mtag-gate')
            result['restarted'] = restart.get('ok', False)
            result['restart'] = restart
            message = ('Restored and mtag-gate restarted.' if restart.get('ok')
                       else f"Restored, but the restart failed: {restart.get('error')}")
        return success_response(data=result, message=message)


# ── Activity: detections, decisions, barrier commands ───────────────────────

class BoothDetectionsView(BoothReadView):
    """Every tag read the gate saw, with the RSSI it was judged on.

    `since` is the id of the last row the caller already has, which is how the
    page polls at 2-second intervals without re-downloading its own table.
    """

    def get(self, request):
        since = request.query_params.get('since')
        limit = request.query_params.get('limit', 400)
        rows = booth_activity.read_tag_reads(limit=limit, since_id=since)
        identity = booth_probe.gate_identity() if booth_probe.is_booth() else {}
        return success_response(data={
            'reads': rows,
            'last_id': rows[-1]['id'] if rows else (int(since) if since else 0),
            'server_time': time.time(),
            # The thresholds travel with the readings so the chart's bands can
            # never disagree with the gate that produced the points.
            'thresholds': {
                'detect': _as_float(identity.get('rssi_detect')),
                'open_min': _as_float(identity.get('rssi_open_min')),
                'open_max': _as_float(identity.get('rssi_open_max')),
                'window': _as_float(identity.get('rssi_window')),
                'hysteresis': _as_float(identity.get('rssi_hysteresis')),
            },
        })


class BoothEventsView(BoothReadView):
    """The gate's decisions: previews, charges and refusals."""

    def get(self, request):
        since = request.query_params.get('since')
        rows = booth_activity.read_gate_events(
            limit=request.query_params.get('limit', 100), since_id=since)
        return success_response(data={
            'events': rows,
            'last_id': rows[-1]['id'] if rows else (int(since) if since else 0),
            'server_time': time.time(),
        })


class BoothBarrierView(BoothReadView):
    """Barrier commands: what the gate issued, and what the portal queued.

    Two sources, because they answer different questions. The local ring buffer
    is what this gate actually sent to the relay. `pending_gate_opens` is what
    the portal asked for — a row with no `executed_at` means the request reached
    master but this gate never claimed it, which is the signature of a gate that
    is down or pointed at the wrong plaza.
    """

    def get(self, request):
        since = request.query_params.get('since')
        commands = booth_activity.read_barrier_commands(
            limit=request.query_params.get('limit', 100), since_id=since)

        pending = []
        identity = booth_probe.gate_identity() if booth_probe.is_booth() else {}
        try:
            plaza_number = int((identity.get('plaza_id') or '').strip())
        except (TypeError, ValueError):
            plaza_number = None
        if plaza_number is not None:
            try:
                rows = (PendingGateOpen.objects
                        .filter(plaza__plaza_id=plaza_number)
                        .select_related('lane')
                        .order_by('-created_at')[:25])
                pending = [{
                    'id': row.id,
                    'lane': row.lane.lane_number if row.lane else None,
                    'created_at': row.created_at.timestamp(),
                    'executed_at': row.executed_at.timestamp() if row.executed_at else None,
                    'status': 'executed' if row.executed_at else 'pending',
                } for row in rows]
            except Exception as exc:
                logger.debug('[booth] pending_gate_opens read failed: %s', exc)

        return success_response(data={
            'commands': commands,
            'last_id': commands[-1]['id'] if commands else (int(since) if since else 0),
            'portal_requests': pending,
            'server_time': time.time(),
        })


class BoothBarrierOpenView(BoothWriteView):
    """Raise the boom on purpose, by one of two routes.

    Which route is the diagnostic. `via=gate` writes a pending_gate_opens row and
    lets the gate's own poller find it — so a boom that moves proves the whole
    chain, master included. `via=service` posts straight at the local barrier
    service and bypasses the gate entirely — so a boom that moves under that but
    not the other narrows the fault to the gate rather than the relay.
    """

    def post(self, request):
        route = (request.data.get('via') or 'gate').strip().lower()
        if route not in ('gate', 'service'):
            return error_response("via must be 'gate' or 'service'.")

        identity = booth_probe.gate_identity() if booth_probe.is_booth() else {}
        who = getattr(request.user, 'phone', str(request.user))

        if route == 'service':
            import json
            import urllib.error
            import urllib.request

            service_url = (identity.get('barrier_service_url')
                           or 'http://127.0.0.1:3005').rstrip('/')
            target = service_url + booth_probe.BARRIER_CONTROL_PATH
            payload = json.dumps({'action': 'open'}).encode()
            started = time.monotonic()
            try:
                http_request = urllib.request.Request(
                    target, data=payload, method='POST',
                    headers={'Content-Type': 'application/json'})
                # The service does not answer an open until the relay pulse has
                # finished, so this waits on hardware — the same ceiling
                # BarrierBackend uses.
                with urllib.request.urlopen(http_request, timeout=15.0) as response:
                    body = json.loads(response.read().decode() or '{}')
            except (urllib.error.URLError, OSError, ValueError) as exc:
                logger.warning('[booth] %s: direct barrier open failed: %s', who, exc)
                return error_response(
                    f'The barrier service at {service_url} did not accept the open: {exc}',
                    status_code=502)

            ok = bool(body.get('success'))
            logger.warning('[booth] %s opened the barrier directly (ok=%s)', who, ok)
            _record_console_barrier(
                action='open', backend='service', ok=ok,
                detail=f'console:{who}' if ok else str(body.get('error') or body))
            if not ok:
                return error_response(
                    f"The barrier service refused the open: {body.get('error') or body}",
                    status_code=502)
            return success_response(
                data={'via': 'service', 'service_url': service_url,
                      'latency_ms': round((time.monotonic() - started) * 1000, 1),
                      'response': body},
                message='The barrier service accepted the open.')

        # via=gate — the same row the portal's own open button writes.
        try:
            plaza_number = int((identity.get('plaza_id') or '').strip())
        except (TypeError, ValueError):
            return error_response(
                'plaza_id is not set in [gate], so there is no plaza to queue an '
                'open against.', status_code=409)
        try:
            plaza = Plaza.objects.get(plaza_id=plaza_number)
        except Plaza.DoesNotExist:
            return error_response(
                f'No plaza with plaza_id {plaza_number} exists on master.',
                status_code=409)

        lane = None
        lane_number = (identity.get('lane_number') or '').strip()
        if lane_number:
            # lane_number is an IntegerField; a config typo would otherwise
            # reach the ORM as a string and surface as a 500 on the page whose
            # job is to explain the fault.
            try:
                lane = TollLane.objects.filter(
                    plaza_id=plaza.id, lane_number=int(lane_number)).first()
            except ValueError:
                return error_response(
                    f"lane_number '{lane_number}' in [gate] is not an integer — "
                    f"the gate will not start with it either.", status_code=409)

        command = PendingGateOpen.objects.create(plaza=plaza, lane=lane)
        logger.warning('[booth] %s queued gate open #%s at plaza %s',
                       who, command.id, plaza_number)
        return success_response(
            data={'via': 'gate', 'id': command.id, 'plaza': plaza.name,
                  'lane': lane.lane_number if lane else None},
            message=(
                'Queued. The gate polls every second and claims commands newer '
                'than 30 seconds — the boom should move shortly. If it does not, '
                'mtag-gate is not running or is pointed at another plaza.'))


def _record_console_barrier(**kwargs):
    """Log a console-issued barrier command into the same ring buffer as the gate's.

    Written from the web process, which has its own recorder writing the same
    SQLite file — WAL is what makes that safe. Without this, a boom raised from
    the console would appear in the barrier log as nothing at all, and the next
    person reading it would be looking for a ghost.
    """
    try:
        booth_activity.get_recorder().record_barrier(source='console', **kwargs)
    except Exception:
        logger.debug('[booth] could not record console barrier command', exc_info=True)


# ── Balance validator ────────────────────────────────────────────────────────

class BoothBalanceView(BoothReadView):
    """What the gate would find for a tag, without charging anything.

    The lookup runs through the same `preview_tag` the gate uses on a far-field
    read, so the verdict here is the verdict the lane gives — then the record is
    expanded with the details that explain it: the tag's status and expiry, the
    vehicle, the account, and any trip left open.

    A TID is what the reader reports and therefore the primary key here, but a
    tag serial or a plate is accepted too: at a booth the thing in someone's
    hand is usually the tag or the car, not its chip id.
    """

    def get(self, request):
        query = (request.query_params.get('tid')
                 or request.query_params.get('q') or '').strip()
        if not query:
            return error_response(
                'Pass ?tid= a chip TID, a tag serial, or a plate number.')

        from apps.accounts.models import Account
        from apps.tolls.services import MINIMUM_BALANCE, preview_tag
        from apps.vehicles.models import Tag

        normalised = query.replace(' ', '').upper()
        tag = (Tag.objects.select_related('vehicle', 'vehicle__owner')
               .filter(tid=normalised).first())
        matched_on = 'tid'
        if tag is None:
            tag = (Tag.objects.select_related('vehicle', 'vehicle__owner')
                   .filter(tag_serial=normalised).first())
            matched_on = 'tag_serial'
        if tag is None:
            tag = (Tag.objects.select_related('vehicle', 'vehicle__owner')
                   .filter(vehicle__plate_number__iexact=query.strip()).first())
            matched_on = 'plate_number'
        if tag is None:
            return success_response(data={
                'query': query, 'found': False, 'matched_on': None,
                'verdict': {'success': False, 'reason': 'Tag not found'},
                'minimum_balance': str(MINIMUM_BALANCE),
            }, message='No tag, serial or plate matches that.')

        # Always previewed by TID — that is what the reader presents at the
        # barrier, so previewing anything else would answer a question the lane
        # never asks. A tag with no TID cannot be read at all, and says so.
        verdict = (preview_tag(tag.tid) if tag.tid else
                   {'success': False,
                    'reason': 'Tag has no TID registered — the reader cannot match it'})

        vehicle = tag.vehicle
        account = None
        if vehicle is not None:
            account = Account.objects.filter(vehicle=vehicle).first()

        active_trip = None
        if vehicle is not None:
            from apps.tolls.models import TollTrip, TripStatus
            trip = (TollTrip.objects
                    .select_related('entry_plaza')
                    .filter(vehicle=vehicle, status=TripStatus.ACTIVE)
                    .first())
            if trip:
                active_trip = {
                    'id': trip.id,
                    'entry_plaza': trip.entry_plaza.name if trip.entry_plaza else '',
                    'entry_time': trip.entry_time.timestamp() if trip.entry_time else None,
                }

        return success_response(data={
            'query': query,
            'found': True,
            'matched_on': matched_on,
            'verdict': verdict,
            'minimum_balance': str(MINIMUM_BALANCE),
            'tag': {
                'tid': tag.tid or '',
                'tag_serial': tag.tag_serial,
                'epc': tag.epc,
                'status': tag.status,
                'expiry_date': tag.expiry_date.isoformat() if tag.expiry_date else None,
                'last_scanned_at': (tag.last_scanned_at.timestamp()
                                    if tag.last_scanned_at else None),
            },
            'vehicle': {
                'plate_number': vehicle.plate_number,
                'vehicle_type': vehicle.vehicle_type,
                'status': vehicle.status,
            } if vehicle else None,
            'account': {
                'balance': str(account.balance),
                'sufficient': account.balance >= MINIMUM_BALANCE,
                'updated_at': (account.balance_updated_at.timestamp()
                               if account.balance_updated_at else None),
            } if account else None,
            'active_trip': active_trip,
        })


# ── LPR camera ───────────────────────────────────────────────────────────────

class BoothCameraView(BoothReadView):
    """What the camera is configured as, and whether ffmpeg is here to read it."""

    def get(self, request):
        identity = booth_probe.gate_identity() if booth_probe.is_booth() else {}
        url = identity.get('camera_rtsp_url', '')
        return success_response(data={
            'configured': bool(url),
            'rtsp_url': booth_probe.redact_url(url),
            'transport': identity.get('camera_transport', 'tcp'),
            'snapshot_url': booth_probe.redact_url(
                identity.get('camera_snapshot_url', '')),
            'tools': booth_probe.camera_available(),
            # The plate feed itself belongs to quick-toll-system, not to this
            # process; run_anpr_gate subscribes to its WebSocket. Named here so
            # someone looking for "where do plates come from" is not left
            # guessing at the answer.
            'anpr_note': (
                'Plate recognition runs in quick-toll-system (WebSocket :3003), '
                'not in this process. This panel verifies the camera link only.'
            ),
        })


class BoothCameraProbeView(BoothReadView):
    """Open the stream and report what it is. Seconds, not milliseconds."""

    def get(self, request):
        identity = booth_probe.gate_identity() if booth_probe.is_booth() else {}
        started = time.monotonic()
        result = booth_probe.camera_probe(
            identity.get('camera_rtsp_url', ''),
            identity.get('camera_transport', 'tcp'))
        result['elapsed_ms'] = round((time.monotonic() - started) * 1000, 1)
        return success_response(data=result)


class BoothCameraSnapshotView(BoothReadView):
    """One JPEG off the LPR stream.

    Returns an image rather than JSON so the page can point an <img> straight at
    it — which is also why a failure answers with a 502 and a plain-text reason
    instead of the usual envelope: an <img> cannot render an error object, and
    the page reads the reason out of the header.
    """

    def get(self, request):
        identity = booth_probe.gate_identity() if booth_probe.is_booth() else {}
        frame, error = booth_probe.camera_snapshot(
            identity.get('camera_rtsp_url', ''),
            identity.get('camera_transport', 'tcp'))
        if frame is None:
            response = HttpResponse(error or 'no frame', status=502,
                                    content_type='text/plain; charset=utf-8')
            response['X-Camera-Error'] = (error or 'no frame')[:200].replace('\n', ' ')
            return response
        response = HttpResponse(frame, content_type='image/jpeg')
        # Every request is a fresh grab; a cached still would quietly show a
        # lane as it was ten minutes ago.
        response['Cache-Control'] = 'no-store, max-age=0'
        return response


# ── Processes and logs ───────────────────────────────────────────────────────

class BoothLogView(BoothReadView):
    """The tail of a PM2 log, for the lines the ring buffer does not carry.

    Reader connect/disconnect, extended-TID rejections, SDK errors and Django
    tracebacks are printed but not recorded — they are not per-tag facts, so
    they have no row. This is where they show up.
    """

    def get(self, request):
        process = (request.query_params.get('process') or 'mtag-gate').strip()
        lines = request.query_params.get('lines', 200)
        return success_response(data=booth_probe.pm2_log_tail(process, lines))


class BoothRestartView(BoothWriteView):
    """Restart mtag-gate. The lane is down for the few seconds it takes."""

    def post(self, request):
        process = (request.data.get('process') or 'mtag-gate').strip()
        who = getattr(request.user, 'phone', str(request.user))
        logger.warning('[booth] %s restarted %s from the console', who, process)
        result = booth_probe.pm2_restart(process)
        if not result.get('ok'):
            return error_response(
                f"Could not restart {process}: {result.get('error') or result.get('output')}",
                status_code=502)
        return success_response(
            data=result,
            message=f'{process} restarted. It takes a few seconds to reconnect to the reader.')


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
