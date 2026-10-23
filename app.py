"""Desktop timer plus an overlay with one configurable editing shortcut."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
from math import isfinite
import os
from pathlib import Path
import queue
import struct
import sys
import threading
import time
import tkinter as tk

from engine import Observation, TimerEngine
from timings import phase_at, countdown_color, compact_text
from overlay import CompactOverlay
from gamebar_view import GameBarView
from hotkeys import parse_edit_hotkey

RESOURCES = Path(__file__).resolve().parent


def application_directory():
    return Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else RESOURCES


ROOT = application_directory()
CONFIG = ROOT/'settings.json'
SETTINGS_DEFAULTS = {
    'source':'','edit_hotkey':'F10','overlay_font':34,
    'overlay_background_opacity':0.5,'overlay_hidden':False,
    'overlay_anchor_x':0.5,'overlay_anchor_y':0.0,'overlay_x':None,'overlay_y':None,
}
BG,TEXT,MUTED = '#10151c','#edf2f7','#98a7b8'
LOG_ENABLED = True
LOG_LOCK = threading.Lock()


def log_event(kind, **values):
    if not LOG_ENABLED:return
    with LOG_LOCK:
        try:
            path = ROOT/'timer.log.jsonl'
            if path.exists() and path.stat().st_size>2*1024*1024:path.replace(ROOT/'timer.previous.jsonl')
            with path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'time':time.time(),'kind':kind,**values},ensure_ascii=False)+'\n')
        except OSError:pass


def find_source():
    folder = Path(os.environ.get('APPDATA',''))/'Nightreign'
    choices = list(folder.glob('*/NR_TimerTests.sl2'))+list(folder.glob('*/NR0000.sl2'))
    return str(max(choices,key=lambda path:path.stat().st_mtime)) if choices else ''


def write_settings(settings):
    preferences = {key:settings.get(key,default) for key,default in SETTINGS_DEFAULTS.items()}
    path = CONFIG.with_suffix('.tmp')
    path.write_text(json.dumps(preferences,ensure_ascii=False,indent=2),encoding='utf-8')
    path.replace(CONFIG)


def load_settings(create=False):
    values = SETTINGS_DEFAULTS.copy()
    try:
        saved = json.loads(CONFIG.read_text(encoding='utf-8'))
        if not isinstance(saved,dict):saved = {}
        values.update({key:saved[key] for key in values if key in saved})
        # Migrate the old background switch, but never save it again.
        if 'overlay_background_opacity' not in saved and saved.get('overlay_background') is True:
            values['overlay_background_opacity'] = 1.0
        if (values['overlay_anchor_y']==0.02 and values['overlay_x'] is None and values['overlay_y'] is None):
            values['overlay_anchor_y']=0.0
    except (OSError,ValueError,TypeError):pass
    if not isinstance(values['source'],str):values['source'] = ''
    font = values['overlay_font']
    if type(font) is not int or not 20<=font<=72:values['overlay_font'] = 34
    if not isinstance(values['overlay_hidden'],bool):values['overlay_hidden'] = False
    for key,fallback in [('overlay_anchor_x',0.5),('overlay_anchor_y',0.0)]:
        value = values[key]
        if type(value) not in (int,float) or not isfinite(value) or not 0<=value<=1:
            values[key] = fallback
    for key in ('overlay_x','overlay_y'):
        if values[key] is not None and type(values[key]) is not int:values[key] = None
    opacity = values['overlay_background_opacity']
    if type(opacity) not in (int,float) or not isfinite(opacity):opacity = 0.5
    values['overlay_background_opacity'] = max(0.0,min(1.0,opacity))
    try:values['edit_hotkey']=parse_edit_hotkey(values['edit_hotkey'])[0]
    except ValueError:values['edit_hotkey']='F10'
    if create and not CONFIG.exists():write_settings(values)
    return values


class Panel:
    def __init__(self, root, background=True):
        self.root,self.ephemeral = root,not background
        self.settings = load_settings(create=background)
        self.source = self.settings['source'] or find_source()
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.threads = []
        self.engine = TimerEngine()
        self.latest,self.read_error,self.gamebar = None,None,None
        self.last_phase,self.last_tracking,self.last_state_write = None,None,0
        self.root.title('Nightreign auto-timer')
        # Give Windows the full-resolution image; ICO selection can expose a small icon to the shell.
        self.icon_image = tk.PhotoImage(file=str(RESOURCES/'assets'/'nightreign-auto-timer.png'))
        self.root.iconphoto(True,self.icon_image)
        self.shell_icon = None
        self.root.bind('<Map>',lambda event: self.root.after_idle(self.apply_shell_icon)
                       if event.widget is self.root else None,add='+')
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        body = tk.Frame(root,bg=BG,padx=24,pady=14)
        body.pack(fill='both',expand=True)
        self.phase_label = tk.Label(body,text='Waiting for\nexpedition...',bg=BG,fg='#d3d3d3',
                                    font=('Times New Roman',17),justify='center')
        self.phase_label.pack(expand=True)
        self.timer_label = tk.Label(body,text='',bg=BG,fg='#ffffff',font=('Times New Roman',34))
        self.timer_label.pack(expand=True)
        self.hint_label = tk.Label(body,text=f"{self.settings['edit_hotkey']} · edit overlay",bg=BG,fg=MUTED,font=('Segoe UI',8))
        self.hint_label.pack(pady=(8,0))
        self.overlay = CompactOverlay(self)
        self.root.update_idletasks()
        scale = max(1,root.winfo_fpixels('1i')/96)
        width = max(round(240*scale),root.winfo_reqwidth())
        height = max(round(145*scale),root.winfo_reqheight())
        root.geometry(f'{width}x{height}+{round(24*scale)}+{round(60*scale)}')
        root.minsize(width,height)
        if background:
            try:
                self.gamebar = GameBarView()
                (ROOT/'gamebar-url.txt').write_text(self.gamebar.url,encoding='utf-8')
            except OSError as exc:log_event('gamebar_unavailable',error=str(exc))
            for target in (self.watch_save,self.watch_keys):
                thread = threading.Thread(target=target,daemon=True)
                self.threads.append(thread)
                thread.start()
        log_event('app_opened',source=self.source)
        self.tick()

    def apply_shell_icon(self):
        # Set both window icons explicitly: the shell can otherwise enlarge Tk's small class icon.
        if os.name!='nt' or self.stop_event.is_set():return
        api = ctypes.WinDLL('user32')
        api.LoadImageW.argtypes = [wintypes.HINSTANCE,wintypes.LPCWSTR,wintypes.UINT,
                                   ctypes.c_int,ctypes.c_int,wintypes.UINT]
        api.LoadImageW.restype = wintypes.HANDLE
        api.GetAncestor.argtypes = [wintypes.HWND,wintypes.UINT]
        api.GetAncestor.restype = wintypes.HWND
        api.SendMessageW.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        api.SendMessageW.restype = wintypes.LPARAM
        if not self.shell_icon:
            self.shell_icon = api.LoadImageW(None,str(RESOURCES/'assets'/'nightreign-auto-timer.ico'),
                                            1,256,256,0x0010)
        hwnd = api.GetAncestor(self.root.winfo_id(),2)
        if hwnd and self.shell_icon:
            for kind in (0,1):api.SendMessageW(hwnd,0x0080,kind,self.shell_icon)


    def save_settings(self):
        if self.ephemeral:return
        try:
            write_settings(self.settings)
        except OSError as exc:log_event('settings_error',error=str(exc))

    def watch_save(self):
        from save_reader import read_observation
        successful,pending,stable_since,error_text = None,None,0,None
        while not self.stop_event.is_set():
            try:
                candidate = find_source()
                if candidate and candidate!=self.source:
                    current_stamp = Path(self.source).stat().st_mtime if self.source and Path(self.source).exists() else 0
                    candidate_stamp = Path(candidate).stat().st_mtime
                    if candidate_stamp>current_stamp and 0<=time.time()-candidate_stamp<=30:
                        self.source = candidate
                        successful,pending,stable_since = None,None,0
                        self.events.put(('source_changed',candidate))
                if not self.source:raise FileNotFoundError('Nightreign save file not found')
                stat = Path(self.source).stat()
                signature = (stat.st_size,stat.st_mtime_ns)
                if signature!=successful:
                    if pending!=signature:pending,stable_since = signature,time.monotonic()
                    elif time.monotonic()-stable_since>=0.4:
                        value = read_observation(self.source)
                        value['observed_at'] = time.time()
                        self.events.put(('observation',value))
                        successful,error_text,pending = signature,None,None
            except (OSError,ValueError,RuntimeError,struct.error) as exc:
                text = str(exc)
                if text!=error_text:
                    self.events.put(('read_error',text))
                    log_event('read_error',error=text)
                    error_text = text
            self.stop_event.wait(0.25)

    def watch_keys(self):
        if os.name!='nt':return
        user = ctypes.WinDLL('user32',use_last_error=True)
        user.RegisterHotKey.argtypes = [wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
        user.RegisterHotKey.restype = wintypes.BOOL
        user.UnregisterHotKey.argtypes = [wintypes.HWND,ctypes.c_int]
        user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
        shortcut,modifiers,key = parse_edit_hotkey(self.settings['edit_hotkey'])
        registered = bool(user.RegisterHotKey(None,1,modifiers|0x4000,key))
        self.events.put(('hotkey',registered))
        log_event('edit_hotkey',shortcut=shortcut,registered=registered)
        try:
            message = wintypes.MSG()
            while not self.stop_event.is_set():
                while user.PeekMessageW(ctypes.byref(message),None,0x0312,0x0312,1):
                    if message.wParam==1:self.events.put(('edit',None))
                self.stop_event.wait(0.05)
        finally:
            if registered:user.UnregisterHotKey(None,1)

    def tick(self):
        while True:
            try:kind,value = self.events.get_nowait()
            except queue.Empty:break
            if kind=='observation':
                self.latest = value
                self.read_error = None
                sample = Observation(value['clock_seconds'],value['saved_at'],value['observed_at'],value['play_time_ms'],
                                     value.get('expedition_active'),value.get('map_id'),value.get('location_unloaded'))
                result = self.engine.observe(sample,time.monotonic())
                log_event('save_clock',clock=value['clock_seconds'],saved_at=value['saved_at'],
                          play_time_ms=value['play_time_ms'],expedition_active=value.get('expedition_active'),
                          map_id=value.get('map_id'),location_unloaded=value.get('location_unloaded'),result=result)
                if result:log_event(result,day=self.engine.day)
            elif kind=='read_error':self.read_error = value
            elif kind=='source_changed':
                self.engine.reset_source()
                log_event('source_changed',source=value)
            elif kind=='edit':self.overlay.toggle_edit()
            elif kind=='hotkey' and not value:
                self.hint_label.configure(text=f"{self.settings['edit_hotkey']} is already used by another app",fg='#ebbc78')
        now,wall = time.monotonic(),time.time()
        if not self.ephemeral:
            result = self.engine.observe_window(self.overlay.game is not None,now)
            if result:log_event(result)
        elapsed = self.engine.elapsed(now)
        phase = phase_at(self.engine.day,elapsed)
        title,clock = compact_text(phase,self.read_error is not None)
        self.phase_label.configure(text=title)
        self.timer_label.configure(text=clock,fg=countdown_color(phase))
        self.root.title('Nightreign auto-timer'+(f' · Day {self.engine.day}' if self.engine.day else ''))
        self.overlay.render(self.engine.day,phase,'',self.read_error is not None)
        status = self.engine.origin
        if self.gamebar:self.gamebar.publish(self.engine.day,phase,status,self.settings,self.read_error is not None)
        phase_id = (self.engine.day,phase.key)
        if phase_id!=self.last_phase:
            self.last_phase = phase_id
            log_event('phase_changed',day=self.engine.day,phase=phase.key,elapsed=elapsed)
        tracking = self.overlay.snapshot()
        tracking_id = (tracking['status'],tracking['game']['hwnd'] if tracking['game'] else None)
        if tracking_id!=self.last_tracking:
            self.last_tracking = tracking_id
            log_event('window_tracking',**tracking)
        if not self.ephemeral and now-self.last_state_write>=1:
            self.last_state_write = now
            try:
                state = {'day':self.engine.day,'source':'save','process_memory':False,
                         'save_session_suspended':self.engine.suspended_run is not None,
                         'started_at':wall-elapsed if self.engine.started_at is not None else None,
                         'origin':self.engine.origin,'phase':phase.key,'elapsed':elapsed,'overlay':tracking}
                path = ROOT/'runtime-state.tmp'
                path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
                path.replace(ROOT/'runtime-state.json')
            except OSError:pass
        if not self.stop_event.is_set():self.root.after(200,self.tick)

    def close(self):
        if self.stop_event.is_set():return
        self.stop_event.set()
        self.save_settings()
        if self.gamebar:self.gamebar.close()
        for thread in self.threads:thread.join(timeout=1)
        log_event('app_closed')
        self.root.destroy()
        if self.shell_icon:
            api = ctypes.WinDLL('user32')
            api.DestroyIcon.argtypes = [wintypes.HICON]
            api.DestroyIcon.restype = wintypes.BOOL
            api.DestroyIcon(self.shell_icon)
            self.shell_icon = None


def main():
    global LOG_ENABLED
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--resume-day',type=int,choices=(1,2,3),help=argparse.SUPPRESS)
    parser.add_argument('--resume-start',type=float,help=argparse.SUPPRESS)
    args = parser.parse_args()
    LOG_ENABLED = not args.self_test
    if (args.resume_day is None)!=(args.resume_start is None):parser.error('Resuming requires a day and a start time.')
    if args.resume_start is not None and not 0<=time.time()-args.resume_start<86400:parser.error('Invalid resume start time.')
    if os.name=='nt':
        try:
            shell = ctypes.WinDLL('shell32')
            shell.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
            shell.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
            shell.SetCurrentProcessExplicitAppUserModelID('Nightreign.AutoTimer')
        except (AttributeError,OSError):pass
        api = ctypes.WinDLL('user32')
        try:
            api.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            api.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError,OSError):pass
    root = tk.Tk();root.withdraw()
    panel = Panel(root,background=not args.self_test)
    if args.resume_day is not None:
        panel.engine.start(args.resume_day,time.monotonic(),time.time()-args.resume_start,
                           'Automatic start · estimated from save file')
        log_event('session_resumed',day=args.resume_day,started_at=args.resume_start)
    if args.self_test:
        from tests.gui_smoke import run
        run(panel,root)
        return
    root.after(150,lambda:(root.deiconify(),panel.overlay.show()))
    root.mainloop()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        log_event('fatal_error',error=repr(exc))
        raise
