"""Soft horizontal edges on our own layered HUD window; no game access."""
import ctypes
from ctypes import wintypes


def side_alphas(width, opacity, interactive=False):
    edge=max(1,width*.24)
    result=[]
    for x in range(width):
        t=min(1,min(x,width-1-x)/edge)
        smooth=t*t*(3-2*t)
        result.append(max(1 if interactive else 0,round(255*opacity*smooth)))
    return result


class BitmapHeader(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),
              ('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),
              ('image_size',wintypes.DWORD),('xppm',wintypes.LONG),('yppm',wintypes.LONG),
              ('colors',wintypes.DWORD),('important',wintypes.DWORD)]


class Blend(ctypes.Structure):
    _fields_=[('operation',wintypes.BYTE),('flags',wintypes.BYTE),
              ('alpha',wintypes.BYTE),('format',wintypes.BYTE)]


class SoftBackground:
    def __init__(self):
        self.signature=None
        self.alphas=[]

    def paint(self, hwnd, position, size, opacity, interactive, hud_top, hud_height):
        signature=(size,opacity,interactive,hud_top,hud_height)
        if signature==self.signature:return
        width,height=size
        alphas=side_alphas(width,opacity,interactive)
        row=bytes(component for a in alphas for component in
                  (round(13*a/255),round(10*a/255),round(8*a/255),a))
        empty=bytes((0,0,0,1 if interactive else 0))*width
        pixels=b''.join(row if hud_top<=y<hud_top+hud_height else empty for y in range(height))
        user=ctypes.WinDLL('user32',use_last_error=True)
        gdi=ctypes.WinDLL('gdi32',use_last_error=True)
        user.GetDC.argtypes=[wintypes.HWND];user.GetDC.restype=wintypes.HDC
        user.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
        gdi.CreateCompatibleDC.argtypes=[wintypes.HDC];gdi.CreateCompatibleDC.restype=wintypes.HDC
        gdi.CreateDIBSection.argtypes=[wintypes.HDC,ctypes.POINTER(BitmapHeader),wintypes.UINT,
                                     ctypes.POINTER(ctypes.c_void_p),wintypes.HANDLE,wintypes.DWORD]
        gdi.CreateDIBSection.restype=wintypes.HBITMAP
        gdi.SelectObject.argtypes=[wintypes.HDC,wintypes.HGDIOBJ];gdi.SelectObject.restype=wintypes.HGDIOBJ
        gdi.DeleteObject.argtypes=[wintypes.HGDIOBJ];gdi.DeleteDC.argtypes=[wintypes.HDC]
        user.UpdateLayeredWindow.argtypes=[wintypes.HWND,wintypes.HDC,ctypes.POINTER(wintypes.POINT),
            ctypes.POINTER(wintypes.SIZE),wintypes.HDC,ctypes.POINTER(wintypes.POINT),
            wintypes.COLORREF,ctypes.POINTER(Blend),wintypes.DWORD]
        screen=user.GetDC(None)
        memory=bitmap=old=None
        try:
            if not screen:raise ctypes.WinError(ctypes.get_last_error())
            memory=gdi.CreateCompatibleDC(screen)
            if not memory:raise ctypes.WinError(ctypes.get_last_error())
            header=BitmapHeader(ctypes.sizeof(BitmapHeader),width,-height,1,32,0,0,0,0,0,0)
            bits=ctypes.c_void_p()
            bitmap=gdi.CreateDIBSection(screen,ctypes.byref(header),0,ctypes.byref(bits),None,0)
            if not bitmap or not bits:raise ctypes.WinError(ctypes.get_last_error())
            old=gdi.SelectObject(memory,bitmap)
            ctypes.memmove(bits,pixels,len(pixels))
            point=wintypes.POINT(*position);dimensions=wintypes.SIZE(width,height)
            origin=wintypes.POINT(0,0);blend=Blend(0,0,255,1)
            if not user.UpdateLayeredWindow(hwnd,screen,ctypes.byref(point),ctypes.byref(dimensions),
                    memory,ctypes.byref(origin),0,ctypes.byref(blend),2):
                raise ctypes.WinError(ctypes.get_last_error())
            self.signature,self.alphas=signature,alphas
        finally:
            if old:gdi.SelectObject(memory,old)
            if bitmap:gdi.DeleteObject(bitmap)
            if memory:gdi.DeleteDC(memory)
            if screen:user.ReleaseDC(None,screen)
