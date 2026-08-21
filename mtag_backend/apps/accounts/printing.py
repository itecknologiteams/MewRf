"""Topup receipt printing (ESC/POS over CUPS `lp`).

Option B from docs/superpowers/specs/2026-06-18-topup-receipt-printing-design.md:
the MewRf backend builds the ESC/POS byte stream itself (mirroring
quick-toll-system's proven layout) and prints to the same 80mm POS80 thermal
printer via `lp -d POS80 -o raw <tmpfile>`.

The receipt layout is topup-specific (not the toll EXIT/ENTRY receipt). Printing
is best-effort: `print_topup_receipt` never raises — it returns True/False and
logs, so a print failure can never roll back a committed topup.
"""
import logging
import os
import subprocess
import tempfile
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger(__name__)

# ESC/POS control bytes
ESC = 0x1B
GS = 0x1D
LF = 0x0A

W = 48  # chars per line on 80mm paper at normal font

# Cached logo raster (logo rarely changes; build once per process).
# Sentinel object means "not built yet"; None means "build failed / no logo".
_LOGO_UNSET = object()
_logo_cache = _LOGO_UNSET


def _lr(left: str, right: str) -> bytes:
    """A 'label .... value' row padded to the full 48-col width."""
    gap = max(1, W - len(left) - len(right))
    return (left + ' ' * gap + right + '\n').encode('ascii', 'replace')


def _dash() -> bytes:
    return ('-' * W + '\n').encode('ascii')


def _eq() -> bytes:
    return ('=' * W + '\n').encode('ascii')


def _center(s: str) -> bytes:
    return s.encode('ascii', 'replace')


def _logo_escpos():
    """Load RECEIPT_LOGO_PATH, dither to 1-bit, emit a centered `GS v 0`
    raster. Returns bytes, or None if no logo / Pillow missing / any error.
    Result is cached after the first call.

    Uses Floyd-Steinberg dithering to preserve mid-tone details (e.g., orange
    stripes) in the 1-bit thermal printer output."""
    global _logo_cache
    if _logo_cache is not _LOGO_UNSET:
        return _logo_cache

    path = getattr(settings, 'RECEIPT_LOGO_PATH', '')
    if not path or not os.path.exists(path):
        logger.info("Receipt logo not found at %s — printing text-only header", path)
        _logo_cache = None
        return None
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not installed — printing receipt without logo")
        _logo_cache = None
        return None

    try:
        img = Image.open(path).convert('L')  # grayscale
        target_w = 256  # ~32mm POS logo width (proper thermal receipt size)
        if img.width != target_w:
            target_h = max(1, round(img.height * target_w / img.width))
            img = img.resize((target_w, target_h))
        pw, ph = img.width, img.height

        # Floyd-Steinberg dithering for better 1-bit conversion of mid-tones
        data = [[float(img.getpixel((x, y))) for x in range(pw)] for y in range(ph)]

        for y in range(ph):
            for x in range(pw):
                old_val = data[y][x]
                new_val = 255.0 if old_val > 127.5 else 0.0
                data[y][x] = new_val
                err = old_val - new_val

                if x + 1 < pw:
                    data[y][x + 1] += err * 7 / 16
                if y + 1 < ph:
                    if x - 1 >= 0:
                        data[y + 1][x - 1] += err * 3 / 16
                    data[y + 1][x] += err * 5 / 16
                    if x + 1 < pw:
                        data[y + 1][x + 1] += err * 1 / 16

        bytes_per_row = (pw + 7) // 8
        bitmap = bytearray(bytes_per_row * ph)
        for y in range(ph):
            row = y * bytes_per_row
            for x in range(pw):
                if data[y][x] < 127.5:  # dithered black pixel
                    bitmap[row + (x >> 3)] |= 1 << (7 - (x & 7))

        header = bytes([
            GS, 0x76, 0x30, 0x00,
            bytes_per_row & 0xFF, (bytes_per_row >> 8) & 0xFF,
            ph & 0xFF, (ph >> 8) & 0xFF,
        ])
        _logo_cache = header + bytes(bitmap)
        return _logo_cache
    except Exception:
        logger.exception("Failed to rasterize receipt logo %s", path)
        _logo_cache = None
        return None


def _amount(value) -> Decimal:
    """Receipt figures arrive as strings; a bad one must not stop the print."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _build_receipt_bytes(data: dict) -> bytes:
    """Build the topup-receipt ESC/POS byte stream (80mm / 48 cols)."""
    p = bytearray()
    p += bytes([ESC, 0x40])          # initialize
    p += bytes([ESC, 0x61, 0x01])    # center

    logo = _logo_escpos()
    if logo:
        p += logo
        p += bytes([LF])

    # Title: TOPUP RECEIPT (double width + height)
    p += bytes([ESC, 0x21, 0x30])
    p += _center('TOPUP RECEIPT\n')
    p += bytes([ESC, 0x21, 0x00])
    p += bytes([LF])

    p += bytes([ESC, 0x61, 0x00])    # left
    p += _eq()
    p += _lr('Receipt #:', str(data.get('receipt_no', '')))
    p += _lr('Date/Time:', str(data.get('datetime', '')))
    p += _dash()
    p += _lr('Consumer:', str(data.get('consumer_name', '')))
    if data.get('vehicle_reg'):
        p += _lr('Vehicle Reg:', str(data.get('vehicle_reg')))
    if data.get('tid'):
        p += _lr('TID:', str(data.get('tid')))
    if data.get('expiry_date'):
        p += _lr('Tag Valid Till:', str(data.get('expiry_date')))
    p += _dash()
    # Only registrations carry a charge; showing a Rs.0.00 line on every repeat
    # topup would just invite the question of what it is.
    charge = _amount(data.get('service_charge'))
    if charge > 0:
        p += _lr('Cash Received:', 'Rs.' + str(data.get('cash_received', '')))
        p += _lr('Service Charge:', 'Rs.' + str(data.get('service_charge')))
    p += _lr('Amount Added:', 'Rs.' + str(data.get('amount', '')))
    if data.get('balance_before') is not None:
        p += _lr('Previous Balance:', 'Rs.' + str(data.get('balance_before')))
    p += _lr('New Balance:', 'Rs.' + str(data.get('balance_after', '')))
    p += _lr('Payment:', str(data.get('payment', 'CASH')))
    if data.get('operator'):
        p += _lr('Operator:', str(data.get('operator')))
    p += _eq()

    p += bytes([ESC, 0x61, 0x01])    # center
    p += bytes([ESC, 0x21, 0x08])    # bold
    p += _center('Thank you\n')
    p += bytes([ESC, 0x21, 0x00])
    p += _center('Malir Expressway Limited\n')
    p += _center('Powered by iTecknologi Group\n')

    p += b'\n\n\n'
    p += bytes([GS, 0x56, 0x41, 0x03])  # full cut
    return bytes(p)


def print_topup_receipt(data: dict) -> bool:
    """Print a topup receipt on the POS80 CUPS printer. Best-effort: returns
    True if the `lp` job was submitted, False otherwise (never raises).

    `data` keys: receipt_no, datetime, consumer_name, vehicle_reg, tid,
    expiry_date, amount, cash_received, service_charge, balance_before,
    balance_after, payment, operator.
    """
    if not getattr(settings, 'TOPUP_RECEIPT_PRINT_ENABLED', False):
        logger.debug("Topup receipt printing disabled (TOPUP_RECEIPT_PRINT_ENABLED=False)")
        return False

    printer = getattr(settings, 'POS_PRINTER_NAME', 'POS80')
    tmp_path = None
    try:
        payload = _build_receipt_bytes(data)
        fd, tmp_path = tempfile.mkstemp(prefix='topup-escpos-', suffix='.bin')
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)
        result = subprocess.run(
            ['lp', '-d', printer, '-o', 'raw', tmp_path],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            logger.error("lp print failed (rc=%s): %s", result.returncode,
                         result.stderr.decode('utf-8', 'replace').strip())
            return False
        logger.info("Topup receipt sent to %s (receipt %s)", printer, data.get('receipt_no'))
        return True
    except Exception:
        logger.exception("Topup receipt print error")
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
