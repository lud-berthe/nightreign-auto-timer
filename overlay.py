"""Two-line overlay with inline editing, anchored to Nightreign's client area."""
import ctypes
from ctypes import wintypes
import os
import tkinter as tk
from tkinter import font as tkfont

from game_window import GameWindowTracker, anchored_position, relative_position
from layered_background import SoftBackground
from timings import countdown_color, compact_text, overlay_active

KEY = '#010101'
HUD_SCALE = .88


class ShadowControl(tk.Canvas):
    """Readable floating text without an opaque button/label rectangle."""
    def __init__(self, master, text='', command=None):
        super().__init__(master,bg=KEY,highlightthickness=0,borderwidth=0,cursor='hand2')
        self.text,self.command=text,command
        self.shadows=[self.create_text(0,0,fill='#000000') for _ in range(8)]
        self.foreground=self.create_text(0,0,fill='#ffffff')
        self.bind('<Configure>',lambda event:self.draw())
        if command:self.bind('<ButtonRelease-1>',lambda event:self.invoke())
        self.set_font(('Segoe UI',-11,'bold'))

    def set_text(self, text):
        self.text=text
        self.draw()

    def set_font(self, font, padx=6, pady=3):
        self.font=tkfont.Font(self,font=font)
        self.stroke=max(1,round(self.font.metrics('linespace')/15))
        self.configure(width=self.font.measure(self.text)+2*padx,
                       height=self.font.metrics('linespace')+2*pady)
        for item in [*self.shadows,self.foreground]:self.itemconfigure(item,font=self.font)
        self.draw()

    def draw(self):
        x,y=self.winfo_width()/2,self.winfo_height()/2
        s=self.stroke
        offsets=((-s,0),(s,0),(0,-s),(0,s),(-s,-s),(-s,s),(s,-s),(s,s))
        for item,(dx,dy) in zip(self.shadows,offsets):
            self.coords(item,x+dx,y+dy);self.itemconfigure(item,text=self.text)
        self.coords(self.foreground,x,y);self.itemconfigure(self.foreground,text=self.text)

    def invoke(self):
        if self.command:return self.command()


class OpacitySlider(tk.Canvas):
    def __init__(self, master):
        super().__init__(master,bg=KEY,highlightthickness=0,borderwidth=0,height=24,cursor='hand2')
        self.value,self.scale,self.command = 0,1,None
        self.bind('<Configure>',lambda event:self.draw())
        self.bind('<Button-1>',self.change_at)
        self.bind('<B1-Motion>',self.change_at)

    def set(self, value):
        self.value = max(0,min(100,round(float(value))))
        self.draw()
        if self.command:self.command(str(self.value))

    def get(self):return self.value

    def set_scale(self, scale):
        self.scale = scale
        self.configure(height=round(24*scale),width=round(150*scale))
        self.draw()

    def change_at(self, event):
        inset = 9*self.scale
        self.set(100*(event.x-inset)/max(1,self.winfo_width()-2*inset))

    def draw(self):
        self.delete('all')
        inset = 9*self.scale
        end,y = max(inset,self.winfo_width()-inset),self.winfo_height()/2
        x = inset+(end-inset)*self.value/100
        self.create_line(inset,y,end,y,fill='#000000',width=max(4,round(6*self.scale)),capstyle='round')
        self.create_line(inset,y,end,y,fill='#536172',width=max(2,round(3*self.scale)),capstyle='round')
        self.create_line(inset,y,x,y,fill='#b8c2cc',width=max(2,round(2*self.scale)),capstyle='round')
        radius = 4*self.scale
        self.create_oval(x-radius,y-radius,x+radius,y+radius,fill='#ffffff',outline='#000000',width=max(1,round(self.scale)))


class CompactOverlay:
    def __init__(self, panel):
        self.panel = panel
        # A click-through backdrop lets the background fade independently
        # while the native text stays fully opaque. No separate editor window.
        self.backdrop = tk.Toplevel(panel.root)
        self.backdrop.withdraw()
        self.backdrop.title('Nightreign auto-timer · Overlay background')
        self.backdrop.overrideredirect(True)
        self.backdrop.configure(bg='#080a0d')
        self.backdrop.attributes('-topmost',True)
        self.soft_background = SoftBackground()
        self.window = tk.Toplevel(panel.root)
        self.window.withdraw()
        self.window.title('Nightreign auto-timer · Overlay')
        self.window.overrideredirect(True)
        self.window.attributes('-topmost',True)
        self.canvas = tk.Canvas(self.window,bg=KEY,highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.phase_shadow = [self.canvas.create_text(0,0,fill='#000000',anchor='n',justify='center') for _ in range(8)]
        self.clock_shadow = [self.canvas.create_text(0,0,fill='#000000',anchor='n') for _ in range(8)]
        self.phase_item = self.canvas.create_text(0,0,fill='#d3d3d3',anchor='n',justify='center')
        self.clock_item = self.canvas.create_text(0,0,fill='#ffffff',anchor='n')
        self.hidden = bool(panel.settings.get('overlay_hidden',False))
        self.editing = False
        self.phase_visible = False
        self.editor = tk.Frame(self.canvas,bg=KEY)
        self.opacity_label = ShadowControl(self.editor)
        self.opacity_label.pack(fill='x')
        self.opacity_scale = OpacitySlider(self.editor)
        self.opacity_scale.set(round(panel.settings.get('overlay_background_opacity',0)*100))
        self.opacity_scale.command = self.set_background_opacity
        self.opacity_scale.pack(fill='x')
        row = tk.Frame(self.editor,bg=KEY);row.pack(fill='x')
        self.edit_buttons = []
        for title,command in [('Reset',self.reset_position),('Hide',self.toggle_visible),('Done',self.toggle_edit)]:
            button = ShadowControl(row,text=title,command=command)
            button.pack(side='left',expand=True,fill='x',padx=2)
            self.edit_buttons.append(button)
            if title=='Hide':self.hide_button = button
        self.editor_item = self.canvas.create_window(0,0,window=self.editor,anchor='n',state='hidden')
        self.opacity_save_after = None
        self.drag_origin = None
        self.control_press = None
        self.tracker = GameWindowTracker()
        self.game = None
        self.api = self.tracker.user
        self.handles = {}
        self.text_signature = self.render_signature = None
        self.visibility_signature = self.backdrop_signature = None
        if self.api:
            self.api.GetParent.argtypes = [wintypes.HWND]
            self.api.GetParent.restype = wintypes.HWND
            self.api.GetWindowRect.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
            self.api.SetWindowPos.argtypes = [wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,
                                             ctypes.c_int,ctypes.c_int,wintypes.UINT]
        self.follow_status = 'not_found'
        self.last_position = None
        self.dpi = 96
        self.size = (240,100)
        self.phase_text,self.clock_text = 'Waiting for\nexpedition...',''
        self.clock_color = '#ffffff'
        self.apply_style()
        self.canvas.bind('<ButtonPress-1>',self.begin_drag)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.end_drag)
        self.backdrop.bind('<ButtonPress-1>',self.background_press)
        self.backdrop.bind('<B1-Motion>',self.background_motion)
        self.backdrop.bind('<ButtonRelease-1>',self.background_release)
        self.window.update_idletasks()
        x,y = panel.settings.get('overlay_x'),panel.settings.get('overlay_y')
        self.move(x if x is not None else (self.window.winfo_screenwidth()-self.size[0])//2,
                  y if y is not None else 24)
        self.set_interactive(False)
        if not panel.ephemeral:self.window.after(50,self.follow_tick)

    def hwnd(self, window=None):
        target = window or self.window
        if target not in self.handles:self.handles[target] = self.api.GetParent(target.winfo_id())
        return self.handles[target]

    def set_interactive(self, editing):
        if os.name!='nt':return
        self.set_window_interactive(self.backdrop,editing)
        self.set_window_interactive(self.window,editing)
        for widget in (self.canvas,self.backdrop):widget.configure(cursor='fleur' if editing else '')

    def set_window_interactive(self, window, editing):
        self.window.update_idletasks()
        api = ctypes.WinDLL('user32',use_last_error=True)
        get,put = api.GetWindowLongPtrW,api.SetWindowLongPtrW
        get.argtypes,get.restype = [wintypes.HWND,ctypes.c_int],ctypes.c_ssize_t
        put.argtypes,put.restype = [wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t],ctypes.c_ssize_t
        handle = self.hwnd(window)
        # Keep the HUD independent of the desktop window's minimized state.
        put(handle,-8,0)
        style = get(handle,-20)|0x00080000|0x00000080|0x08000000
        style = style & ~0x00000020 if editing else style|0x00000020
        ctypes.set_last_error(0)
        result = put(handle,-20,style)
        if not result and ctypes.get_last_error():raise ctypes.WinError(ctypes.get_last_error())

    def move(self, x, y, force=False):
        x,y = int(x),int(y)
        if not force and self.last_position==(x,y):return
        self.visibility_signature = self.backdrop_signature = None
        self.last_position = (x,y)
        self.window.update_idletasks()
        if os.name=='nt':
            api = self.api
            rect = wintypes.RECT()
            for window in (self.window,self.backdrop):
                handle = self.hwnd(window)
                if api.GetWindowRect(handle,ctypes.byref(rect)) and (rect.left,rect.top)==(x,y):continue
                api.SetWindowPos(handle,None,x,y,0,0,0x0001|0x0004|0x0010)
        else:
            for window in (self.window,self.backdrop):window.geometry(f'+{x}+{y}')

    def apply_style(self):
        self.text_signature = self.render_signature = None
        self.visibility_signature = self.backdrop_signature = None
        self.window.configure(bg=KEY)
        self.canvas.configure(bg=KEY)
        self.window.attributes('-alpha',1.0)
        if os.name=='nt':self.window.attributes('-transparentcolor',KEY)
        opacity = self.panel.settings.get('overlay_background_opacity',0)
        self.opacity_label.set_text(f'Opacity {round(opacity*100)}%')
        self.hide_button.set_text('Show' if self.hidden else 'Hide')
        scale = self.dpi/96
        clock_px = round(self.panel.settings.get('overlay_font',34)*scale*HUD_SCALE)
        phase_px = max(12,round(clock_px/1.7))
        self.phase_font = tkfont.Font(self.window,family='Times New Roman',size=-phase_px)
        self.clock_font = tkfont.Font(self.window,family='Times New Roman',size=-clock_px)
        self.padding = max(3,round(5*scale*HUD_SCALE))
        width = max(self.phase_font.measure('Waiting for expedition...'),self.clock_font.measure('00:00'))+2*self.padding+8
        height = self.phase_font.metrics('linespace')+self.clock_font.metrics('linespace')+2*self.padding
        self.preview_height = height
        ui_font = ('Segoe UI',-max(11,round(11*scale)),'bold')
        self.opacity_label.set_font(ui_font)
        self.opacity_scale.set_scale(scale)
        for button in self.edit_buttons:button.set_font(ui_font,padx=round(6*scale),pady=round(2*scale))
        self.editor.update_idletasks()
        width = max(width,self.editor.winfo_reqwidth()+2*self.padding)
        self.hud_size = (width,height)
        self.controls_above = self.editing and self.panel.settings.get('overlay_anchor_y',0)>0.5
        self.preview_offset = self.editor.winfo_reqheight()+self.padding if self.controls_above else 0
        self.canvas.itemconfigure(self.editor_item,state='normal' if self.editing else 'hidden')
        if self.editing:
            height += self.editor.winfo_reqheight()+self.padding
        self.size = (width,height)
        self.window.geometry(f'{width}x{height}')
        self.backdrop.geometry(f'{width}x{height}')
        self.canvas.configure(width=width,height=height)
        for item in [self.phase_item]+self.phase_shadow:self.canvas.itemconfigure(item,font=self.phase_font)
        for item in [self.clock_item]+self.clock_shadow:self.canvas.itemconfigure(item,font=self.clock_font)
        self.draw_text(self.clock_color)

    def draw_text(self, color='#ffffff'):
        width,height = self.size
        x,y = width/2,self.padding+self.preview_offset
        clock_y = y+self.phase_font.metrics('linespace')
        phase_text,clock_text = ('Edit','0:00') if self.editing else (self.phase_text,self.clock_text)
        if self.editing and self.hidden:phase_text,clock_text='',''
        if self.editing:color = '#ffffff'
        signature = (self.size,self.padding,self.preview_offset,self.preview_height,self.controls_above,
                     str(self.phase_font),str(self.clock_font),self.dpi,self.editing,self.hidden,phase_text,clock_text,color)
        if signature==self.text_signature:return
        self.text_signature = signature
        stroke = max(1,round(self.dpi/96))
        offsets = [(-stroke,0),(stroke,0),(0,-stroke),(0,stroke),
                   (-stroke,-stroke),(stroke,-stroke),(-stroke,stroke),(stroke,stroke)]
        for phase_id,clock_id,(dx,dy) in zip(self.phase_shadow,self.clock_shadow,offsets):
            self.canvas.coords(phase_id,x+dx,y+dy)
            self.canvas.coords(clock_id,x+dx,clock_y+dy)
            self.canvas.itemconfigure(phase_id,text=phase_text)
            self.canvas.itemconfigure(clock_id,text=clock_text)
        self.canvas.coords(self.phase_item,x,y)
        self.canvas.coords(self.clock_item,x,clock_y)
        self.canvas.itemconfigure(self.phase_item,text=phase_text,fill='#edf2f7' if self.editing else '#d3d3d3')
        self.canvas.itemconfigure(self.clock_item,text=clock_text,fill=color)
        self.canvas.coords(self.editor_item,x,self.padding if self.controls_above else self.preview_height)
        self.canvas.itemconfigure(self.editor_item,width=width-2*self.padding)

    def render(self, day, phase, status, read_error=False):
        self.phase_visible = overlay_active(day)
        self.phase_text,self.clock_text = compact_text(phase,read_error) if self.phase_visible else ('','')
        color = self.clock_color = countdown_color(phase)
        signature = (self.phase_visible,self.phase_text,self.clock_text,color)
        if signature!=self.render_signature:
            self.render_signature = signature
            if self.window.winfo_ismapped() or not self.phase_visible or self.editing:self.draw_text(color)
            self.update_visibility()

    def follow_tick(self):
        if self.panel.stop_event.is_set():return
        self.game = self.tracker.current()
        game = self.game
        if game is None:self.follow_status = 'not_found'
        elif game.minimized or game.width<=0 or game.height<=0:self.follow_status = 'minimized'
        elif not game.foreground and not self.editing:self.follow_status = 'inactive'
        else:self.follow_status = 'following'
        if game and not game.minimized and game.width>0 and game.height>0:
            if game.dpi!=self.dpi:
                self.dpi = game.dpi
                self.apply_style()
            if not self.drag_origin and (self.phase_visible or self.editing):
                x,y = anchored_position(game,self.hud_size,
                    self.panel.settings.get('overlay_anchor_x',0.5),
                    self.panel.settings.get('overlay_anchor_y',0))
                position = (x,y-self.preview_offset)
                if position!=self.last_position:self.move(*position)
        self.update_visibility()
        self.window.after(50,self.follow_tick)

    def update_visibility(self):
        signature = (self.follow_status,self.hidden,self.phase_visible,self.editing,self.last_position,
                     self.size,self.preview_offset,self.preview_height,self.panel.settings.get('overlay_background_opacity',0))
        if signature==self.visibility_signature:return
        allowed = self.follow_status=='following' or self.editing
        if not self.editing and (self.hidden or not self.phase_visible or not allowed):
            if self.window.winfo_ismapped():self.window.withdraw()
        elif not self.window.winfo_ismapped():
            self.draw_text(self.clock_color)
            self.window.deiconify()
            self.window.update_idletasks()
            if self.last_position:self.move(*self.last_position,force=True)
            if os.name=='nt':
                api = self.api
                api.SetWindowPos(self.hwnd(),wintypes.HWND(-1),0,0,0,0,0x0001|0x0002|0x0010)
        self.sync_backdrop()
        self.visibility_signature = signature

    def sync_backdrop(self):
        opacity = self.panel.settings.get('overlay_background_opacity',0)
        if not self.window.winfo_ismapped() or (not self.editing and opacity<=0):
            if self.backdrop.winfo_ismapped():self.backdrop.withdraw()
            self.backdrop_signature = None
            return
        if not self.backdrop.winfo_ismapped():
            self.backdrop.deiconify()
            if self.last_position:self.move(*self.last_position,force=True)
            self.backdrop_signature = None
        signature = (self.last_position,self.size,opacity,self.hidden,self.editing,self.preview_offset,self.preview_height)
        if signature==self.backdrop_signature:return
        if os.name=='nt':
            api = self.api
            api.SetWindowPos(self.hwnd(self.backdrop),self.hwnd(),0,0,0,0,0x0001|0x0002|0x0010)
            self.soft_background.paint(self.hwnd(self.backdrop),self.last_position,self.size,
                0 if self.hidden else opacity,self.editing,self.preview_offset,self.preview_height)
        self.backdrop_signature = signature

    def set_background_opacity(self, value):
        opacity = max(0,min(100,float(value)))/100
        self.panel.settings['overlay_background_opacity'] = opacity
        self.opacity_label.set_text(f'Opacity {round(opacity*100)}%')
        self.sync_backdrop()
        if self.opacity_save_after:self.window.after_cancel(self.opacity_save_after)
        self.opacity_save_after = self.window.after(200,self.save_opacity)

    def save_opacity(self):
        self.opacity_save_after = None
        self.panel.save_settings()

    def show(self):
        if self.panel.ephemeral:self.follow_status = 'following'
        self.update_visibility()

    def toggle_visible(self):
        self.hidden = not self.hidden
        self.panel.settings['overlay_hidden'] = self.hidden
        self.panel.save_settings()
        self.hide_button.set_text('Show' if self.hidden else 'Hide')
        self.draw_text(self.canvas.itemcget(self.clock_item,'fill'))
        self.update_visibility()

    def toggle_edit(self):
        x,y = self.last_position
        y += self.preview_offset
        self.editing = not self.editing
        self.drag_origin = None
        self.apply_style()
        self.move(x,y-self.preview_offset)
        self.set_interactive(self.editing)
        self.draw_text(self.canvas.itemcget(self.clock_item,'fill'))
        self.update_visibility()

    def reset_position(self):
        self.panel.settings.update(overlay_anchor_x=0.5,overlay_anchor_y=0,overlay_x=None,overlay_y=None)
        self.panel.save_settings()
        self.apply_style()
        if self.game and not self.game.minimized:self.move(*anchored_position(self.game,self.hud_size))
        else:self.move((self.window.winfo_screenwidth()-self.size[0])//2,24)

    def begin_drag(self, event):
        if self.editing:self.drag_origin = (event.x_root,event.y_root,*self.last_position)

    def control_at(self, event):
        if not self.editing:return None
        for widget in (self.opacity_scale,*self.edit_buttons):
            x,y=widget.winfo_rootx(),widget.winfo_rooty()
            if x<=event.x_root<x+widget.winfo_width() and y<=event.y_root<y+widget.winfo_height():return widget

    def background_press(self, event):
        self.control_press=self.control_at(event)
        if self.control_press is self.opacity_scale:self.background_motion(event)
        elif self.control_press is None:self.begin_drag(event)

    def background_motion(self, event):
        if self.control_press is self.opacity_scale:
            inset=9*self.opacity_scale.scale
            width=max(1,self.opacity_scale.winfo_width()-2*inset)
            self.opacity_scale.set(100*(event.x_root-self.opacity_scale.winfo_rootx()-inset)/width)
        elif self.control_press is None:self.drag(event)

    def background_release(self, event):
        control,self.control_press=self.control_press,None
        if control is self.opacity_scale:
            self.control_press=control;self.background_motion(event);self.control_press=None
        elif control is not None:
            if self.control_at(event) is control:control.invoke()
        else:self.end_drag(event)

    def drag(self, event):
        if self.drag_origin and self.editing:
            x,y,wx,wy = self.drag_origin
            self.move(wx+event.x_root-x,wy+event.y_root-y)

    def end_drag(self, event):
        if self.drag_origin:
            self.drag_origin = None
            x,y = self.last_position
            y += self.preview_offset
            self.panel.settings.update(overlay_x=x,overlay_y=y)
            if self.game and not self.game.minimized:
                ax,ay = relative_position(self.game,(x,y),self.hud_size)
                self.panel.settings.update(overlay_anchor_x=ax,overlay_anchor_y=ay)
            self.panel.save_settings()
            self.apply_style()
            self.move(x,y-self.preview_offset)

    def snapshot(self):
        game = self.game
        return {'status':self.follow_status,'position':self.last_position,'size':self.size,
                'hidden':self.hidden,'phase_visible':self.phase_visible,'visible':bool(self.window.winfo_ismapped()),
                'background_opacity':self.panel.settings.get('overlay_background_opacity',0),
                'editing':self.editing,'game':vars(game) if game else None}
