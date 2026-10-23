"""Opt-in automatic launch/close; no game-process handles or memory access."""
import os
from pathlib import Path
import subprocess


RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_VALUE = 'NightreignAutoTimer'


class GameLifecycle:
    def __init__(self, close_delay=5, initially_running=False):
        self.running = initially_running
        self.missing_since = None
        self.close_delay = close_delay

    def observe(self, present, now):
        if present:
            self.missing_since = None
            if not self.running:
                self.running = True
                return 'opened'
        elif self.running:
            if self.missing_since is None:self.missing_since = now
            elif now-self.missing_since >= self.close_delay:
                self.running = False
                self.missing_since = None
                return 'closed'
        return None


class InstanceLock:
    def __init__(self, directory, role):
        self.path = Path(directory)/f'.timer-{role}.lock'
        self.stream = None

    def acquire(self):
        if self.stream is not None:return True
        stream = self.path.open('a+b')
        if stream.tell()==0:
            stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.stream = stream
        return True

    def release(self):
        if self.stream is None:return
        try:
            self.stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.stream = None


def instance_running(directory, role):
    lock = InstanceLock(directory,role)
    if not lock.acquire():return True
    lock.release()
    return False


def configure_startup(enabled, command):
    import winreg
    if enabled:
        value = subprocess.list2cmdline([*command,'--watch'])
        if len(value)>260:raise ValueError('Move the app to a shorter folder path to enable automatic opening.')
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,RUN_KEY,0,winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key,RUN_VALUE,0,winreg.REG_SZ,value)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY,0,winreg.KEY_SET_VALUE) as key:
                try:winreg.DeleteValue(key,RUN_VALUE)
                except FileNotFoundError:pass
        except FileNotFoundError:pass


def launch_process(command, directory):
    environment = os.environ.copy()
    # A one-file child must own its extracted runtime and survive its parent.
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return subprocess.Popen(command,cwd=directory,env=environment,
                            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
