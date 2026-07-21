"""Local Ollama process control: is it installed, is the port busy, start, stop.

Separate from ``api.py`` because these are OS concerns, not HTTP ones. Nothing
here is Windows-only, but Windows gets its own branch where the POSIX approach
doesn't apply (``taskkill`` instead of signals, ``CREATE_NO_WINDOW`` so starting
the server doesn't flash a console).

**On installing Ollama**: this app never silently downloads and runs an
installer. Ollama is a large native program; fetching an executable from the
internet and executing it without the user seeing what is happening is not
something a management tool should do quietly. Instead it offers two explicit
routes — the system package manager (winget on Windows, brew on macOS), or
opening the official download page in a browser — and the caller confirms first.
"""

import os
import shutil
import socket
import subprocess
import sys

DOWNLOAD_PAGE = 'https://ollama.com/download'

_WINDOWS = sys.platform.startswith('win')
# Names the server/tray program runs under, per platform.
_PROCESS_NAMES = ('ollama.exe', 'ollama app.exe') if _WINDOWS else ('ollama',)


def _no_window():
    """Popen kwargs that keep a console from flashing up on Windows."""
    if _WINDOWS and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def binary_path():
    """Full path to the ``ollama`` executable, or None if it isn't on PATH."""
    return shutil.which('ollama')


def installed():
    return binary_path() is not None


def cli_version(timeout=5):
    """``ollama --version`` output, or '' if it can't be read."""
    if not installed():
        return ''
    try:
        out = subprocess.run(['ollama', '--version'], capture_output=True,
                             text=True, timeout=timeout, **_no_window())
        return (out.stdout or out.stderr or '').strip()
    except Exception:                                        # noqa: BLE001
        return ''


def port_in_use(host='127.0.0.1', port=11434, timeout=0.6):
    """True if something is listening — distinguishes 'not running' from
    'running but not answering the API', which are different problems."""
    host = str(host).replace('http://', '').replace('https://', '').split('/')[0]
    if ':' in host:
        host = host.split(':', 1)[0]
    try:
        with socket.create_connection((host or '127.0.0.1', int(port)), timeout):
            return True
    except OSError:
        return False


def start_server(host='127.0.0.1', port=11434):
    """Launch ``ollama serve`` detached on the given address.

    Ollama reads its bind address from OLLAMA_HOST, so a non-default port is
    passed through the environment. Returns (ok, message).
    """
    if not installed():
        return False, ('Ollama is not installed, or not on PATH. Use '
                       '"Install Ollama" first.')
    env = dict(os.environ)
    env['OLLAMA_HOST'] = '{}:{}'.format(host, port)
    try:
        subprocess.Popen(['ollama', 'serve'], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         **_no_window())
        return True, 'Starting Ollama on {}:{}…'.format(host, port)
    except Exception as exc:                                 # noqa: BLE001
        return False, 'Could not start Ollama: {}'.format(exc)


def stop_server():
    """Terminate the local Ollama processes. Returns (ok, message).

    Targets only the known Ollama process names — never a PID discovered by
    scanning the port, which could belong to something else entirely.
    """
    stopped, errors = [], []
    for name in _PROCESS_NAMES:
        try:
            if _WINDOWS:
                out = subprocess.run(['taskkill', '/F', '/IM', name],
                                     capture_output=True, text=True, timeout=15,
                                     **_no_window())
                if out.returncode == 0:
                    stopped.append(name)
                elif 'not found' not in (out.stdout + out.stderr).lower():
                    errors.append((out.stderr or out.stdout).strip())
            else:
                out = subprocess.run(['pkill', '-f', name], capture_output=True,
                                     text=True, timeout=15)
                if out.returncode == 0:
                    stopped.append(name)
        except FileNotFoundError:
            errors.append('No process-control tool available on this system.')
        except Exception as exc:                             # noqa: BLE001
            errors.append(str(exc))
    if stopped:
        return True, 'Stopped: {}'.format(', '.join(stopped))
    if errors:
        return False, '; '.join(errors)
    return False, 'Ollama did not appear to be running.'


def package_manager():
    """The install route available here: 'winget', 'brew', or None."""
    if _WINDOWS and shutil.which('winget'):
        return 'winget'
    if sys.platform == 'darwin' and shutil.which('brew'):
        return 'brew'
    return None


def install_command():
    """The exact command an install would run, so it can be shown before it is."""
    pm = package_manager()
    if pm == 'winget':
        return ['winget', 'install', '--id', 'Ollama.Ollama', '-e',
                '--accept-package-agreements', '--accept-source-agreements']
    if pm == 'brew':
        return ['brew', 'install', 'ollama']
    return None


def install(timeout=1800):
    """Install Ollama via the system package manager. Returns (ok, message).

    Only ever called after the user has confirmed the command shown to them.
    Linux is deliberately not automated: its official route pipes a shell script
    from the internet, which this app will not run on a user's behalf.
    """
    cmd = install_command()
    if not cmd:
        return False, ('No supported package manager found. Use "Open Download '
                       'Page" and install Ollama from the official site.')
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:                                 # noqa: BLE001
        return False, 'Install failed to start: {}'.format(exc)
    if out.returncode == 0:
        return True, ('Ollama installed. If it is still not detected, close and '
                      'reopen this app so it picks up the new PATH.')
    detail = (out.stderr or out.stdout or '').strip()
    return False, 'Install failed: {}'.format(detail[:400] or out.returncode)


def models_dir():
    """Where Ollama keeps its models, for the disk-usage hint."""
    custom = os.environ.get('OLLAMA_MODELS')
    if custom:
        return custom
    return os.path.join(os.path.expanduser('~'), '.ollama', 'models')


def models_dir_size():
    """Bytes used by the models directory, or None if it can't be read."""
    root = models_dir()
    if not os.path.isdir(root):
        return None
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                continue
    return total
