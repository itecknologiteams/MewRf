"""The release version of this deployment.

A booth is "up to date" when the VERSION file it has on disk matches master's.
The file ships inside mtag_backend/, so master and every booth get it from the
same deploy that carries the code — there is nothing extra to stamp at deploy
time, but it does mean the number only changes when someone edits VERSION.
"""

from functools import lru_cache
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / 'VERSION'

UNKNOWN = 'unknown'


@lru_cache(maxsize=1)
def get_code_version() -> str:
    """This install's release version, or 'unknown' if VERSION is missing."""
    try:
        version = VERSION_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        return UNKNOWN
    return version.splitlines()[0].strip() if version else UNKNOWN
