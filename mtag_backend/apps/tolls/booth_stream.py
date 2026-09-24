"""Live view of the LPR camera, without letting it cost the lane anything.

The camera on a booth is H.265 at 1080p. No browser plays RTSP, and Chrome on
Linux does not decode H.265 either, so the picture has to be transcoded here
whatever we do. What is left is choosing the cheapest thing that still answers
the question the panel exists for — "is the camera up, aimed at the lane, and in
focus" — and that is MJPEG over `multipart/x-mixed-replace`: an <img> plays it
with no player library, which matters on a booth with no internet to fetch one
from.

The whole design is about not becoming the reason a barrier is slow.

  ONE ffmpeg, shared.   Viewers attach to a running pipeline rather than each
                        starting their own. Two engineers on the same lane cost
                        what one costs.

  It stops on its own.  ffmpeg is killed LINGER seconds after the last viewer
                        leaves. The linger exists so a page reload does not pay
                        for a restart, and it is short so a closed tab does not
                        leave a transcode running.

  It cannot run for ever. MAX_SESSION_SECONDS ends the stream even with a viewer
                        attached. A console left open on a spare monitor
                        overnight is the realistic failure, and this is what
                        makes it self-correcting.

  Few viewers.          MAX_VIEWERS is small because each one holds a gunicorn
                        thread for as long as it watches, and the booth has
                        four in total (gunicorn.conf.py). Past the cap the
                        endpoint refuses rather than quietly eating the booth's
                        capacity to answer anything else.

  It yields to the gate. The ffmpeg process is niced down. The gate is a separate
                        process with its own CPU claim, but a booth PC is small
                        and a transcode must never be what delays a boom.

  Slow viewers drop frames. Each viewer has a one-frame queue. A viewer that
                        cannot keep up loses frames instead of blocking the
                        reader and stalling everyone else.
"""

import logging
import os
import queue
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

# Seconds the pipeline stays up after the last viewer leaves.
LINGER_SECONDS = 5.0
# Hard ceiling on one continuous stream, however many people are watching.
MAX_SESSION_SECONDS = 600.0
# Each viewer holds one gunicorn thread; the booth has four.
MAX_VIEWERS = 2
# How long a viewer waits for a frame before giving up on the pipeline.
FRAME_WAIT_SECONDS = 15.0
# Startup grace: H.265 over RTSP takes a moment to produce its first frame.
FIRST_FRAME_SECONDS = 20.0

JPEG_SOI = b'\xff\xd8'
JPEG_EOI = b'\xff\xd9'

BOUNDARY = 'mtagframe'


class _Viewer:
    """One browser watching. Holds at most one frame."""

    def __init__(self):
        self.frames: queue.Queue = queue.Queue(maxsize=1)
        self.dropped = 0

    def offer(self, frame: bytes):
        try:
            self.frames.put_nowait(frame)
        except queue.Full:
            # Replace the stale frame rather than queue behind it: a live view
            # showing the lane as it was two seconds ago is worse than one that
            # skips.
            try:
                self.frames.get_nowait()
                self.frames.put_nowait(frame)
            except (queue.Empty, queue.Full):
                pass
            self.dropped += 1


class CameraStream:
    """The single shared ffmpeg pipeline for this booth's camera."""

    def __init__(self):
        self._lock = threading.Lock()
        self._viewers: list = []
        self._process = None
        self._reader = None
        self._latest = None
        self._latest_at = 0.0
        self._started_at = 0.0
        self._idle_since = 0.0
        self._frames = 0
        self._error = ''
        self._settings = {}
        self._stopping = False

    # ── What the console asks ────────────────────────────────────────────────

    def status(self) -> dict:
        with self._lock:
            running = self._process is not None and self._process.poll() is None
            uptime = (time.monotonic() - self._started_at) if running else 0.0
            return {
                'running': running,
                'viewers': len(self._viewers),
                'max_viewers': MAX_VIEWERS,
                'frames': self._frames,
                'uptime_seconds': round(uptime, 1),
                'seconds_remaining': (
                    round(max(0.0, MAX_SESSION_SECONDS - uptime), 1) if running else 0.0),
                'last_frame_age': (
                    round(time.monotonic() - self._latest_at, 1) if self._latest_at else None),
                'error': self._error,
                'settings': dict(self._settings),
                'max_session_seconds': MAX_SESSION_SECONDS,
            }

    def latest_frame(self):
        """The most recent frame, for the stills endpoint — free while live."""
        with self._lock:
            if self._latest and (time.monotonic() - self._latest_at) < 5.0:
                return self._latest
        return None

    # ── Viewers ──────────────────────────────────────────────────────────────

    def attach(self, url, settings):
        """Join the stream, starting it if nobody else has. Returns a viewer.

        Raises RuntimeError when the booth is already carrying as many viewers
        as it will. Refusing is deliberate: silently accepting a third would
        take the booth from "one spare thread" to "none", and the thing that
        stops answering is the console itself.
        """
        with self._lock:
            if len(self._viewers) >= MAX_VIEWERS:
                raise RuntimeError(
                    f'{len(self._viewers)} people are already watching this camera, '
                    f'which is all this booth will carry. Each viewer holds one of '
                    f'the four request threads the booth has.'
                )
            viewer = _Viewer()
            self._viewers.append(viewer)
            self._idle_since = 0.0
            needs_start = self._process is None or self._process.poll() is not None
            if needs_start:
                self._start_locked(url, settings)
            return viewer

    def detach(self, viewer):
        with self._lock:
            if viewer in self._viewers:
                self._viewers.remove(viewer)
            if not self._viewers:
                # Linger rather than stop: a page reload detaches and reattaches
                # within a second, and restarting ffmpeg for that means the
                # viewer waits for the RTSP handshake all over again.
                self._idle_since = time.monotonic()

    def frames_for(self, viewer):
        """Yield multipart chunks to an ALREADY ATTACHED viewer.

        Attaching is deliberately not done here. A generator function does not
        run a line of its body until it is first iterated, so a version of this
        that called attach() itself raised its "too many viewers" error midway
        through the response body — long after the status line had gone out as
        200. The caller could not catch it and the browser got a truncated
        stream instead of a 429. The view attaches first, while it can still
        choose a status code, and hands the viewer in here.
        """
        deadline = time.monotonic() + FIRST_FRAME_SECONDS
        try:
            while True:
                try:
                    frame = viewer.frames.get(timeout=1.0)
                except queue.Empty:
                    with self._lock:
                        failed = self._error
                        alive = self._process is not None and self._process.poll() is None
                        have_had_frames = self._frames > 0
                    if failed:
                        return
                    if not alive and have_had_frames:
                        return          # session ended normally (or timed out)
                    if not have_had_frames and time.monotonic() > deadline:
                        return          # never produced a picture
                    if have_had_frames and time.monotonic() > deadline + FRAME_WAIT_SECONDS:
                        return
                    continue
                deadline = time.monotonic() + FRAME_WAIT_SECONDS
                yield (
                    b'--' + BOUNDARY.encode() + b'\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n'
                    + frame + b'\r\n'
                )
        finally:
            # Reached whether the browser closed the tab, the generator was
            # garbage collected, or the stream ended — so a viewer is never
            # left counted against MAX_VIEWERS.
            self.detach(viewer)

    # ── The pipeline ─────────────────────────────────────────────────────────

    def _start_locked(self, url, settings):
        from . import booth_probe

        binary = booth_probe._ffmpeg_binary('ffmpeg')
        if not binary:
            self._error = 'ffmpeg is not installed on this booth'
            return
        if not url:
            self._error = 'no camera configured — set [camera] rtsp_url'
            return

        width = int(settings.get('width') or 640)
        fps = float(settings.get('fps') or 6)
        quality = int(settings.get('quality') or 7)
        transport = 'udp' if settings.get('transport') == 'udp' else 'tcp'

        command = [binary, '-nostdin', '-loglevel', 'error']
        if url.startswith(('rtsp://', 'rtsps://')):
            command += ['-rtsp_transport', transport]
        command += [
            '-i', url,
            '-an',                       # the camera sends pcm_alaw; we want none of it
            '-sn', '-dn',
            # Scale first, then drop frames: -2 keeps the height even, which the
            # JPEG encoder requires, and preserves the aspect ratio.
            '-vf', f'scale={width}:-2,fps={fps}',
            '-f', 'mjpeg',
            '-q:v', str(quality),
            # Two threads is plenty for 1080p H.265 at this output size, and
            # leaves the rest of a small booth CPU to the lane.
            '-threads', '2',
            '-',
        ]

        def _deprioritise():
            # The gate is what earns money; a transcode is not. POSIX only —
            # guarded because booth_bootstrap supports Windows booths too.
            try:
                os.nice(10)
            except (AttributeError, OSError):
                pass

        try:
            self._process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0, preexec_fn=_deprioritise if os.name == 'posix' else None,
            )
        except (OSError, ValueError) as exc:
            self._error = f'could not start ffmpeg: {exc}'
            self._process = None
            return

        self._error = ''
        self._frames = 0
        self._latest = None
        self._latest_at = 0.0
        self._started_at = time.monotonic()
        self._idle_since = 0.0
        self._stopping = False
        self._settings = {'width': width, 'fps': fps, 'quality': quality,
                          'transport': transport}
        self._reader = threading.Thread(
            target=self._read_frames, args=(self._process,),
            name='camera-stream', daemon=True)
        self._reader.start()
        logger.info('[camera] Stream started — %dpx %.1ffps q%d', width, fps, quality)

    def _read_frames(self, process):
        """Split ffmpeg's MJPEG stdout into frames and hand them to viewers."""
        buffer = b''
        try:
            while True:
                if self._should_stop(process):
                    break
                chunk = process.stdout.read(32768)
                if not chunk:
                    break
                buffer += chunk

                # MJPEG on a pipe is bare JPEGs back to back: find each SOI…EOI.
                while True:
                    start = buffer.find(JPEG_SOI)
                    if start < 0:
                        # No frame starting; do not let junk accumulate.
                        if len(buffer) > 1 << 20:
                            buffer = b''
                        break
                    end = buffer.find(JPEG_EOI, start + 2)
                    if end < 0:
                        # Partial frame — keep it, drop anything before it.
                        if start:
                            buffer = buffer[start:]
                        break
                    frame = buffer[start:end + 2]
                    buffer = buffer[end + 2:]
                    self._publish(frame)
        except (OSError, ValueError) as exc:
            with self._lock:
                if not self._stopping:
                    self._error = f'stream read failed: {exc}'
        finally:
            self._finish(process)

    def _should_stop(self, process):
        with self._lock:
            if self._process is not process:
                return True
            now = time.monotonic()
            if now - self._started_at > MAX_SESSION_SECONDS:
                logger.info('[camera] Stream hit its %.0fs ceiling — stopping',
                            MAX_SESSION_SECONDS)
                self._stopping = True
                return True
            if not self._viewers and self._idle_since and \
                    now - self._idle_since > LINGER_SECONDS:
                self._stopping = True
                return True
        return False

    def _publish(self, frame):
        with self._lock:
            self._latest = frame
            self._latest_at = time.monotonic()
            self._frames += 1
            viewers = list(self._viewers)
        for viewer in viewers:
            viewer.offer(frame)

    def _finish(self, process):
        stderr = b''
        try:
            process.kill()
        except OSError:
            pass
        try:
            stderr = process.stderr.read() or b''
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=3)
        except (subprocess.SubprocessError, OSError):
            pass
        for stream in (process.stdout, process.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass

        with self._lock:
            if self._process is process:
                self._process = None
                had_frames = self._frames > 0
                if stderr and not had_frames and not self._stopping:
                    from . import booth_probe
                    detail = booth_probe.redact_url(
                        stderr.decode('utf-8', 'replace').strip())
                    self._error = detail[:400] or 'ffmpeg produced no frames'
                self._stopping = False
        logger.info('[camera] Stream stopped after %d frames', self._frames)

    def stop(self):
        """End the stream now, whoever is watching."""
        with self._lock:
            process = self._process
            self._stopping = True
            self._viewers = []
        if process is not None:
            try:
                process.kill()
            except OSError:
                pass


_stream = None
_stream_lock = threading.Lock()


def get_stream() -> CameraStream:
    global _stream
    with _stream_lock:
        if _stream is None:
            _stream = CameraStream()
        return _stream
