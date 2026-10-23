"""Phase countdowns; each day is anchored to its observed arrival."""
from dataclasses import dataclass
from math import ceil


# Calibrated expedition schedule; these values are not user preferences.
FIRST_CLOSING_START = 271.75
FIRST_CLOSING_DURATION = 180.35
SECOND_CLOSING_START = 662.1
SECOND_CLOSING_DURATION = 177.1


@dataclass(frozen=True)
class Phase:
    key: str
    title: str
    remaining: float | None
    duration: float | None
    index: int


def countdown_color(phase):
    return '#ff766b' if phase.remaining is not None and phase.remaining < 60 else '#ffffff'


def compact_text(phase, read_error=False):
    title = ('Waiting for game data' if read_error else
             'Waiting for\nexpedition...' if phase.key=='idle' else
             'Day 3' if phase.key=='final' else 'Boss' if phase.key=='boss' else
             'closing now' if phase.key.endswith('shrink') else 'closing in')
    if phase.remaining is None:return title,''
    seconds = max(0,ceil(phase.remaining))
    return title,f'{seconds//60}:{seconds%60:02}'


def overlay_active(day):return day in (1,2)


def phase_at(day, elapsed):
    if day == 0:
        return Phase('idle', 'Waiting for expedition...', None, None, -1)
    if day == 3:
        return Phase('final', 'Final boss', None, None, 4)
    first = FIRST_CLOSING_START
    second = SECOND_CLOSING_START
    first_shrink = FIRST_CLOSING_DURATION
    second_shrink = SECOND_CLOSING_DURATION
    phases = (
        ('first_wait', 'First closing in', 0, first),
        ('first_shrink', 'First closing now', first, first+first_shrink),
        ('second_wait', 'Second closing in', first+first_shrink, second),
        ('second_shrink', 'Second closing now', second, second+second_shrink),
    )
    for index, (key, title, start, end) in enumerate(phases):
        if elapsed < end:
            return Phase(key, title, max(0, end-elapsed), end-start, index)
    return Phase('boss', f'Night boss {day}', None, None, 4)
