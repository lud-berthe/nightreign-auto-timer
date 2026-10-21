"""Read only window bounds via User32; no game-process handle is opened."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
import time


@dataclass(frozen=True)
class GameWindow:
    hwnd: int
    pid: int
    x: int
    y: int
    width: int
    height: int
    minimized: bool = False
    foreground: bool = True
    dpi: int = 96


def anchored_position(game, size, anchor_x=0.5, anchor_y=0):
    width, height = size
    x = game.x + round(game.width*anchor_x-width/2)
    y = game.y + round(game.height*anchor_y)
    return (max(game.x,min(x,game.x+max(0,game.width-width))),
            max(game.y,min(y,game.y+max(0,game.height-height))))


def relative_position(game, position, size):
    x,y = position
    return (max(0,min(1,(x+size[0]/2-game.x)/max(1,game.width))),
            max(0,min(1,(y-game.y)/max(1,game.height))))


class GameWindowTracker:
    TITLE = 'ELDEN RING NIGHTREIGN'

    def __init__(self):
        self.hwnd = None
        self.next_search = 0
        self.user = ctypes.WinDLL('user32',use_last_error=True) if os.name=='nt' else None
        if not self.user:return
        u = self.user
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextW.argtypes = [wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        u.GetClientRect.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        for name in ('IsWindow','IsWindowVisible','IsIconic'):
            getattr(u,name).argtypes = [wintypes.HWND]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        u.GetForegroundWindow.restype = wintypes.HWND
        if hasattr(u,'GetDpiForWindow'):u.GetDpiForWindow.argtypes = [wintypes.HWND]
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        u.EnumWindows.argtypes = [self.callback_type,wintypes.LPARAM]

    def title(self, hwnd):
        count = self.user.GetWindowTextLengthW(hwnd)
        text = ctypes.create_unicode_buffer(count+1)
        self.user.GetWindowTextW(hwnd,text,count+1)
        return ' '.join(text.value.upper().split())

    def pid(self, hwnd):
        value = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(value))
        return value.value

    def read_window(self, hwnd):
        u = self.user
        if not u or not u.IsWindow(hwnd):return None
        rect,origin = wintypes.RECT(),wintypes.POINT()
        if not u.GetClientRect(hwnd,ctypes.byref(rect)) or not u.ClientToScreen(hwnd,ctypes.byref(origin)):
            return None
        pid = self.pid(hwnd)
        foreground_pid = self.pid(u.GetForegroundWindow())
        dpi = u.GetDpiForWindow(hwnd) if hasattr(u,'GetDpiForWindow') else 96
        return GameWindow(int(hwnd),pid,origin.x,origin.y,rect.right-rect.left,rect.bottom-rect.top,
                          bool(u.IsIconic(hwnd)),foreground_pid in (pid,os.getpid()),dpi or 96)

    def current(self):
        if not self.user:return None
        if self.hwnd and self.user.IsWindow(self.hwnd) and self.title(self.hwnd)==self.TITLE:
            return self.read_window(self.hwnd)
        self.hwnd = None
        if time.monotonic()<self.next_search:return None
        self.next_search = time.monotonic()+1
        candidates = []
        @self.callback_type
        def inspect(hwnd, unused):
            if self.user.IsWindowVisible(hwnd) and self.title(hwnd)==self.TITLE:
                item = self.read_window(hwnd)
                if item:candidates.append(item)
            return True
        self.user.EnumWindows(inspect,0)
        if candidates:
            item = max(candidates,key=lambda w:w.width*w.height)
            self.hwnd = item.hwnd
            return item
        return None
