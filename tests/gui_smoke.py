"""Windows-only smoke check; operates exclusively on its own test windows."""
import ctypes
from ctypes import wintypes
import time
import tkinter as tk


def run(panel, root):
    from dataclasses import replace
    from game_window import anchored_position
    assert [check.cget('text') for check in panel.automation_checks]==[
        'Open automatically with Nightreign','Close automatically with Nightreign']
    for key,check in zip(('open_with_game','close_with_game'),panel.automation_checks):
        before=panel.settings[key];check.invoke();assert panel.settings[key] is not before
        check.invoke();assert panel.settings[key] is before
    wall = time.time()
    panel.events.put(('observation',dict(clock_seconds=23400,saved_at=wall-2,observed_at=wall-1,play_time_ms=1000)))
    panel.events.put(('observation',dict(clock_seconds=23401,saved_at=wall-0.2,observed_at=wall,play_time_ms=2000)))
    panel.tick()
    assert panel.engine.day==1
    panel.engine.started_at = time.monotonic()-213
    panel.tick()
    assert panel.timer_label.cget('text')=='0:59'
    assert panel.overlay.canvas.itemcget(panel.overlay.clock_item,'text')=='0:59'
    assert panel.timer_label.cget('fg')=='#ff766b'
    target = tk.Toplevel(root);target.title('Timer · test window');target.geometry('800x500+100+100');root.update()
    tracker = panel.overlay.tracker
    api = ctypes.WinDLL('user32');api.GetParent.argtypes=[wintypes.HWND];api.GetParent.restype=wintypes.HWND
    dummy_hwnd = api.GetParent(target.winfo_id())
    panel.overlay.tracker.current = lambda:tracker.read_window(dummy_hwnd)
    panel.overlay.follow_tick();root.update()
    first = panel.overlay.last_position
    target.geometry('1000x600+220+180');root.update()
    panel.overlay.follow_tick();root.update()
    assert panel.overlay.last_position==anchored_position(tracker.read_window(dummy_hwnd),panel.overlay.size)
    actual_rect = wintypes.RECT()
    api.GetWindowRect.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    api.GetWindowRect(panel.overlay.hwnd(),ctypes.byref(actual_rect))
    assert (actual_rect.left,actual_rect.top)==panel.overlay.last_position
    assert panel.overlay.last_position!=first
    captured = tracker.read_window(dummy_hwnd)
    panel.overlay.tracker.current = lambda:replace(captured,minimized=True)
    panel.overlay.follow_tick();root.update()
    assert not panel.overlay.window.winfo_ismapped()
    top_levels = {str(widget) for widget in root.winfo_children() if isinstance(widget,tk.Toplevel)}
    panel.events.put(('edit',None));panel.tick();root.update()
    assert panel.overlay.editing and panel.overlay.editor.winfo_exists()
    assert panel.overlay.editor.master is panel.overlay.canvas
    assert top_levels=={str(widget) for widget in root.winfo_children() if isinstance(widget,tk.Toplevel)}
    assert panel.overlay.canvas.itemcget(panel.overlay.phase_item,'text')=='Edit'
    assert panel.overlay.canvas.itemcget(panel.overlay.clock_item,'text')=='0:00'
    panel.overlay.opacity_scale.set(35);root.update()
    assert panel.settings['overlay_background_opacity']==0.35
    assert float(panel.overlay.window.attributes('-alpha'))==1.0
    assert max(panel.overlay.soft_background.alphas)==round(255*.35)
    assert panel.overlay.soft_background.alphas[0]<max(panel.overlay.soft_background.alphas)
    assert panel.overlay.backdrop.winfo_ismapped()
    background_rect = wintypes.RECT()
    api.GetWindowRect(panel.overlay.hwnd(panel.overlay.backdrop),ctypes.byref(background_rect))
    api.GetWindowRect(panel.overlay.hwnd(),ctypes.byref(actual_rect))
    assert (background_rect.left,background_rect.top,background_rect.right,background_rect.bottom)==(
        actual_rect.left,actual_rect.top,actual_rect.right,actual_rect.bottom)
    assert panel.overlay.canvas.cget('cursor')=='fleur'
    assert panel.overlay.backdrop.cget('cursor')=='fleur'
    from types import SimpleNamespace
    drag_x=actual_rect.left+panel.overlay.padding
    drag_y=actual_rect.top+panel.overlay.preview_offset+panel.overlay.padding
    api.WindowFromPoint.argtypes=[wintypes.POINT];api.WindowFromPoint.restype=wintypes.HWND
    api.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];api.GetAncestor.restype=wintypes.HWND
    hit=api.WindowFromPoint(wintypes.POINT(drag_x,drag_y))
    assert api.GetAncestor(hit,2)==panel.overlay.hwnd(panel.overlay.backdrop)
    original_position=panel.overlay.last_position
    panel.overlay.background_press(SimpleNamespace(x_root=drag_x,y_root=drag_y))
    assert panel.overlay.drag_origin is not None
    moved_event=SimpleNamespace(x_root=drag_x+40,y_root=drag_y+30)
    panel.overlay.background_motion(moved_event)
    assert panel.overlay.last_position==(original_position[0]+40,original_position[1]+30)
    panel.overlay.background_release(moved_event)
    assert panel.overlay.drag_origin is None
    slider = panel.overlay.opacity_scale
    slider.event_generate('<Button-1>',x=1,y=slider.winfo_height()//2)
    slider.event_generate('<B1-Motion>',x=slider.winfo_width()-1,y=slider.winfo_height()//2)
    root.update()
    assert panel.settings['overlay_background_opacity']==1.0
    assert panel.overlay.drag_origin is None
    assert float(panel.overlay.window.attributes('-alpha'))==1.0
    # Transparent parts of the slider/button rectangles receive input
    # through the backdrop, without accidentally dragging the HUD.
    slider_start=SimpleNamespace(x_root=slider.winfo_rootx()+1,y_root=slider.winfo_rooty()+1)
    slider_end=SimpleNamespace(x_root=slider.winfo_rootx()+slider.winfo_width()-1,y_root=slider.winfo_rooty()+1)
    panel.overlay.background_press(slider_start)
    assert panel.settings['overlay_background_opacity']==0
    assert panel.overlay.drag_origin is None
    assert panel.overlay.backdrop.winfo_ismapped()
    panel.overlay.background_motion(slider_end);panel.overlay.background_release(slider_end)
    assert panel.settings['overlay_background_opacity']==1
    hide_point=SimpleNamespace(x_root=panel.overlay.hide_button.winfo_rootx()+1,
                               y_root=panel.overlay.hide_button.winfo_rooty()+1)
    panel.overlay.background_press(hide_point);panel.overlay.background_release(hide_point);root.update()
    assert panel.overlay.hidden and panel.overlay.window.winfo_ismapped()
    assert panel.overlay.canvas.itemcget(panel.overlay.phase_item,'text')==''
    assert panel.overlay.canvas.itemcget(panel.overlay.clock_item,'text')==''
    assert max(panel.overlay.soft_background.alphas)==1
    assert panel.overlay.opacity_scale.winfo_ismapped()
    assert panel.overlay.hide_button.winfo_ismapped()
    assert panel.timer_label.cget('text')=='0:59'
    panel.overlay.toggle_visible()
    assert panel.overlay.canvas.itemcget(panel.overlay.phase_item,'text')=='Edit'
    assert max(panel.overlay.soft_background.alphas)==255
    panel.overlay.reset_position()
    assert panel.settings['overlay_anchor_x']==0.5
    assert panel.settings['overlay_anchor_y']==0
    panel.events.put(('edit',None));panel.tick()
    assert not panel.overlay.editing
    assert panel.overlay.canvas.itemcget(panel.overlay.editor_item,'state')=='hidden'
    panel.overlay.opacity_scale.set(0);root.update()
    assert not panel.overlay.backdrop.winfo_ismapped()
    panel.overlay.tracker.current = lambda:replace(captured,minimized=False,foreground=True)
    panel.settings['overlay_anchor_y']=0.9
    panel.overlay.follow_tick();root.update()
    hud_position = panel.overlay.last_position
    panel.overlay.toggle_edit();root.update()
    assert panel.overlay.controls_above
    assert (panel.overlay.last_position[0],panel.overlay.last_position[1]+panel.overlay.preview_offset)==hud_position
    panel.overlay.toggle_edit();panel.overlay.follow_tick();root.update()
    assert panel.overlay.last_position==hud_position
    panel.overlay.reset_position()
    for day,label in [(3,'Day 3'),(0,'Waiting for\nexpedition...')]:
        if day:panel.engine.start(day,time.monotonic())
        else:panel.engine.stop()
        panel.tick();panel.overlay.follow_tick();root.update()
        assert panel.phase_label.cget('text')==label
        assert panel.timer_label.cget('text')==''
        assert not panel.overlay.window.winfo_ismapped()
        assert panel.overlay.canvas.itemcget(panel.overlay.phase_item,'text')==''
        panel.overlay.toggle_edit();root.update()
        assert panel.overlay.window.winfo_ismapped()
        assert panel.overlay.canvas.itemcget(panel.overlay.phase_item,'text')=='Edit'
        panel.overlay.toggle_edit();root.update()
        assert not panel.overlay.window.winfo_ismapped()
    panel.engine.start(1,time.monotonic())
    panel.tick();panel.overlay.follow_tick();root.update()
    assert panel.overlay.window.winfo_ismapped()
    panel.engine.reset_source();panel.engine.start(1,time.monotonic())
    for offset in (0,5):
        panel.events.put(('observation',dict(clock_seconds=23872,saved_at=wall+offset,
            observed_at=wall+offset,play_time_ms=5000,expedition_active=True,
            map_id=None,location_unloaded=True)))
        panel.tick()
    panel.overlay.follow_tick();root.update()
    assert panel.engine.suspended_run is not None
    assert panel.phase_label.cget('text')=='Waiting for\nexpedition...'
    assert panel.timer_label.cget('text')==''
    assert not panel.overlay.window.winfo_ismapped()
    panel.events.put(('observation',dict(clock_seconds=23945,saved_at=wall+10,
        observed_at=wall+10,play_time_ms=6000,expedition_active=True,
        map_id=None,location_unloaded=True)))
    panel.tick();panel.overlay.follow_tick();root.update()
    assert panel.engine.day==1 and panel.engine.suspended_run is None
    assert panel.overlay.window.winfo_ismapped()
    # Exercise the real close-on-game-exit branch without writing preferences or starting a watcher.
    from unittest.mock import patch
    panel.settings['close_with_game']=True
    with patch.object(panel.game_session,'observe',return_value='closed'),patch.object(panel,'close') as close:
        panel.ephemeral=False
        try:panel.tick();close.assert_called_once()
        finally:panel.ephemeral=True
    root.tk.call(root.protocol('WM_DELETE_WINDOW'))
    assert panel.stop_event.is_set()
    import sys
    if getattr(sys,'frozen',False):
        import shutil,tempfile
        from pathlib import Path
        from lifecycle import launch_process
        with tempfile.TemporaryDirectory(prefix='nr-child-') as folder:
            executable = Path(folder)/'Nightreign auto-timer.exe'
            shutil.copy2(sys.executable,executable)
            child = launch_process([str(executable),'--watch'],folder)
            try:assert child.wait(timeout=20)==0
            finally:
                if child.poll() is None:child.kill();child.wait()
    print('GUI, tracking, editor, Day 3/lobby hiding, save suspension/resume and close checks passed')
    return
