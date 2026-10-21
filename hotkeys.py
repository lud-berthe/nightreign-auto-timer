"""Editable Windows shortcut syntax for the overlay editor."""


def parse_edit_hotkey(value):
    if not isinstance(value,str):raise ValueError('Shortcut must be text')
    parts=[part.strip().upper() for part in value.split('+')]
    if not parts or any(not part for part in parts):raise ValueError('Empty shortcut key')
    names={'CTRL':('Ctrl',2),'CONTROL':('Ctrl',2),'ALT':('Alt',1),'SHIFT':('Shift',4)}
    modifiers=0
    for part in parts[:-1]:
        if part not in names:raise ValueError('Unknown shortcut modifier')
        _,flag=names[part]
        if modifiers&flag:raise ValueError('Duplicate shortcut modifier')
        modifiers|=flag
    key=parts[-1]
    keys={'SPACE':('Space',0x20),'TAB':('Tab',0x09),'ENTER':('Enter',0x0d),
          'ESCAPE':('Escape',0x1b),'INSERT':('Insert',0x2d),'DELETE':('Delete',0x2e),
          'HOME':('Home',0x24),'END':('End',0x23),'PAGEUP':('PageUp',0x21),
          'PAGEDOWN':('PageDown',0x22),'LEFT':('Left',0x25),'UP':('Up',0x26),
          'RIGHT':('Right',0x27),'DOWN':('Down',0x28)}
    if len(key)==1 and key in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
        label,virtual_key=key,ord(key)
    elif key.startswith('F') and key[1:].isdigit() and 1<=int(key[1:])<=24:
        label,virtual_key=f'F{int(key[1:])}',0x6f+int(key[1:])
    elif key in keys:label,virtual_key=keys[key]
    else:raise ValueError('Unknown shortcut key')
    prefix=[label for label,flag in (('Ctrl',2),('Alt',1),('Shift',4)) if modifiers&flag]
    return '+'.join([*prefix,label]),modifiers,virtual_key
