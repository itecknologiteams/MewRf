"""Pushing code from master to a booth over SSH.

This is deploy_booth.sh's copy/extract/bootstrap sequence, driven from master
instead of a developer's laptop, so an operator can update one lane from the
admin portal. It runs only in booth_deploy_worker — never in a web request.

Two differences from deploy_booth.sh matter, both forced by where it runs now:

  * master's tree has no wheelhouse/. deploy_master.sh excludes those 34MB of
    booth wheels because master installs from PyPI. The booth does not — it has
    no internet — so the purge below KEEPS the booth's existing wheelhouse.
    Deleting it the way deploy_booth.sh does would leave booth_update.sh with
    neither wheels nor PyPI, and it would exit 5 with the lane's services down.

  * every ssh runs with stdin closed (-n). booth_update.sh calls sudo in a few
    places; with no terminal and no stdin, sudo fails immediately instead of
    hanging a worker for the full timeout waiting for a password nobody can type.
"""

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from utils.code_version import get_code_version

BASE_DIR = Path(settings.BASE_DIR)
REMOTE_DIR = 'mtag_backend'
REMOTE_TARBALL = 'mtag_backend_deploy.tar.gz'

# Delimits the two halves of the check script's output so one ssh round trip
# can return both the version and the PM2 table.
_PM2_MARKER = '---PM2---'


class DeployError(Exception):
    """A step failed. The message is written to the job log verbatim."""


# ── SSH plumbing ─────────────────────────────────────────────────────────────

def _ssh_password() -> str:
    return getattr(settings, 'BOOTH_SSH_PASSWORD', '') or ''


def _ssh_user(machine) -> str:
    return machine.ssh_user or getattr(settings, 'BOOTH_SSH_USER', 'iteck')


def _wrap() -> list:
    """sshpass prefix, or nothing when key-based auth is in use."""
    if not _ssh_password():
        return []
    return ['sshpass', '-e']


def _env() -> dict:
    """sshpass reads the password from SSHPASS so it never appears in argv."""
    env = os.environ.copy()
    password = _ssh_password()
    if password:
        env['SSHPASS'] = password
    return env


_SSH_OPTS = [
    '-o', 'StrictHostKeyChecking=accept-new',
    '-o', 'ConnectTimeout=10',
    # Without this a dropped LAN link leaves the worker blocked on a dead
    # socket well past the job timeout.
    '-o', 'ServerAliveInterval=15',
    '-o', 'ServerAliveCountMax=4',
]


def _run(argv: list, timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            env=_env(), check=False,
        )
    except subprocess.TimeoutExpired:
        # Surfaced as an ordinary failed step. A booth that stops answering
        # halfway through an install is a normal field condition, and a
        # traceback in the operator's log would say far less than this does.
        return subprocess.CompletedProcess(
            args=argv, returncode=124, stdout='',
            stderr=f"Timed out after {timeout}s with no response from the booth.",
        )


def ssh(machine, script: str, timeout: int) -> subprocess.CompletedProcess:
    """Run a shell script on the booth. stdin is closed — see the module docstring."""
    argv = [
        *_wrap(), 'ssh', '-n', *_SSH_OPTS,
        '-p', str(machine.ssh_port), f'{_ssh_user(machine)}@{machine.host}',
        script,
    ]
    return _run(argv, timeout)


def scp(machine, local_path: Path, remote_name: str, timeout: int) -> subprocess.CompletedProcess:
    argv = [
        *_wrap(), 'scp', *_SSH_OPTS,
        '-P', str(machine.ssh_port), str(local_path),
        f'{_ssh_user(machine)}@{machine.host}:~/{remote_name}',
    ]
    return _run(argv, timeout)


def sshpass_available() -> bool:
    """A password without sshpass would sit on a prompt no one can answer."""
    if not _ssh_password():
        return True
    return subprocess.run(['which', 'sshpass'], capture_output=True).returncode == 0


# ── Reading a booth's state ──────────────────────────────────────────────────

_CHECK_SCRIPT = f"""
cat {REMOTE_DIR}/VERSION 2>/dev/null | head -1
echo '{_PM2_MARKER}'
pm2 jlist 2>/dev/null || echo '[]'
"""


def check(machine, timeout: int = 60) -> dict:
    """Read the booth's VERSION and PM2 process states over one SSH round trip.

    Returns {reachable, version, pm2, log}. A booth that answers but has no
    VERSION file is running code from before this feature shipped — reported as
    'unknown' rather than an error, since that is a real and expected state.
    """
    result = ssh(machine, _CHECK_SCRIPT, timeout)
    log = _format_result('check', result)

    if result.returncode != 0:
        return {'reachable': False, 'version': '', 'pm2': '', 'log': log}

    raw_version, _, raw_pm2 = result.stdout.partition(_PM2_MARKER)
    version = raw_version.strip() or 'unknown'
    return {
        'reachable': True,
        'version': version,
        'pm2': _summarise_pm2(raw_pm2),
        'log': log,
    }


def _summarise_pm2(raw: str) -> str:
    """`pm2 jlist` → 'mtag-web: online, mtag-gate: online'.

    Falls back to the raw text when PM2 is absent or prints something that is
    not JSON, because "pm2: command not found" is itself the useful answer.
    """
    raw = raw.strip()
    if not raw:
        return ''
    try:
        procs = json.loads(raw)
    except (ValueError, TypeError):
        return raw[:500]
    if not procs:
        return 'no processes'
    return ', '.join(
        f"{p.get('name', '?')}: {(p.get('pm2_env') or {}).get('status', '?')}"
        for p in procs
    )


# ── Building the bundle master ships ─────────────────────────────────────────

def build_bundle(dest_dir: Path) -> Path:
    """Tar master's own code tree into the archive a booth extracts.

    Mirrors deploy_booth.sh's exclude list, plus wheelhouse/ (master does not
    have one) and VERSION explicitly kept so the booth can report what it runs.
    """
    tarball = dest_dir / REMOTE_TARBALL
    plain = dest_dir / REMOTE_TARBALL[:-3]
    parent = BASE_DIR.parent
    name = BASE_DIR.name

    argv = [
        'tar', '-cf', str(plain),
        '--exclude=venv', '--exclude=staticfiles', '--exclude=__pycache__',
        '--exclude=.env', '--exclude=.env.*', '--exclude=rfid_config.ini',
        '--exclude=offline_cache.db', '--exclude=*.pyc', '--exclude=wheelhouse',
        '-C', str(parent), name,
    ]
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise DeployError(f"Could not build the code bundle:\n{result.stderr}")

    # booth_update.sh creates .env from this template when a booth has none, so
    # it must ride along even though the .env* exclude above drops its family.
    example = BASE_DIR / '.env.booth.example'
    if example.exists():
        subprocess.run(
            ['tar', '-rf', str(plain), '-C', str(parent), f'{name}/.env.booth.example'],
            capture_output=True, text=True, check=False,
        )

    subprocess.run(['gzip', '-f', str(plain)], capture_output=True, check=False)
    if not tarball.exists():
        raise DeployError("The code bundle was not produced.")

    # Prove no real .env slipped in rather than trusting the pattern list —
    # the same guard deploy_booth.sh runs before shipping.
    listing = subprocess.run(
        ['tar', '-tzf', str(tarball)], capture_output=True, text=True, check=False,
    ).stdout
    leaked = [
        line for line in listing.splitlines()
        if line.rstrip('/').endswith(('/.env', '/.env.master', '/.env.booth'))
    ]
    if leaked:
        raise DeployError(f"Refusing to ship secrets — bundle contains {leaked}")
    return tarball


# ── Updating a booth ─────────────────────────────────────────────────────────

# Everything the booth must keep across a code push. venv and the config files
# match deploy_booth.sh; wheelhouse is the addition that makes a master-driven
# push safe (see the module docstring).
_PRESERVE = ['venv', '.env', 'rfid_config.ini', 'offline_cache.db', 'staticfiles', 'wheelhouse']

_EXTRACT_SCRIPT = """
set -e
if [ ! -d {remote_dir} ]; then
  echo "!!! {remote_dir} does not exist on this booth — provision it with deploy_booth.sh first" >&2
  exit 3
fi
find {remote_dir} -mindepth 1 -maxdepth 1 {keeps} -exec rm -rf {{}} +
tar -xzf {tarball}
echo "extracted $(cat {remote_dir}/VERSION 2>/dev/null | head -1)"
"""

_UPDATE_SCRIPT = """
cd {remote_dir} && bash booth_update.sh
"""


def update(machine, timeout: int) -> dict:
    """Ship master's code to the booth, reinstall it, and restart PM2.

    Returns {ok, exit_code, log, version}. The archive is copied before anything
    is deleted, so there is no window where the booth has neither the old code
    nor the new.
    """
    parts = []
    keeps = ' '.join(f'! -name {shlex.quote(name)}' for name in _PRESERVE)

    with tempfile.TemporaryDirectory(prefix='mtag-bundle-') as tmp:
        parts.append(f"--- building bundle for version {get_code_version()} ---")
        tarball = build_bundle(Path(tmp))
        parts.append(f"    {tarball.name} ({tarball.stat().st_size // 1024} KB)")

        parts.append(f"--- copying to {machine.host} ---")
        result = scp(machine, tarball, REMOTE_TARBALL, timeout)
        parts.append(_format_result('scp', result))
        if result.returncode != 0:
            return _failed(parts, result.returncode)

    parts.append("--- purging stale code and extracting ---")
    result = ssh(machine, _EXTRACT_SCRIPT.format(
        remote_dir=REMOTE_DIR, keeps=keeps, tarball=REMOTE_TARBALL,
    ), timeout)
    parts.append(_format_result('extract', result))
    if result.returncode != 0:
        return _failed(parts, result.returncode)

    parts.append("--- running booth_update.sh (deps, SDK, PM2 restart) ---")
    result = ssh(machine, _UPDATE_SCRIPT.format(remote_dir=REMOTE_DIR), timeout)
    parts.append(_format_result('booth_update.sh', result))
    if result.returncode != 0:
        parts.append(_explain_exit(result.returncode))
        return _failed(parts, result.returncode)

    return {'ok': True, 'exit_code': 0, 'log': '\n'.join(parts)}


# booth_update.sh documents these; repeating them here turns a bare number in
# the portal into something an operator can act on.
_EXIT_MEANINGS = {
    2: "The booth's .env or rfid_config.ini is missing, or still points at a local "
       "database. Fix it over SSH, then update again.",
    3: "The booth has no mtag_backend directory yet — provision it once with "
       "deploy_booth.sh before updating from here.",
    4: "Node/PM2 is unavailable on the booth, so the services were not restarted. "
       "The code and dependencies are in place; fix PM2 and update again.",
    5: "Python dependencies could not be installed. The booth's wheelhouse may not "
       "match its Python version.",
    7: "The booth cannot reach master's database, so nothing was started.",
}


def _explain_exit(code: int) -> str:
    meaning = _EXIT_MEANINGS.get(code)
    return f"!!! {meaning}" if meaning else f"!!! booth_update.sh exited {code}."


def _format_result(label: str, result: subprocess.CompletedProcess) -> str:
    out = [f"$ {label} (exit {result.returncode})"]
    if result.stdout.strip():
        out.append(result.stdout.rstrip())
    if result.stderr.strip():
        out.append(result.stderr.rstrip())
    return '\n'.join(out)


def _failed(parts: list, exit_code: int) -> dict:
    return {'ok': False, 'exit_code': exit_code, 'log': '\n'.join(parts)}
