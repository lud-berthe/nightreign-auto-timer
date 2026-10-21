"""Automatic timer driven by observed save-clock transitions."""
from dataclasses import dataclass
from math import ceil
from statistics import median

MORNING = 6 * 3600 + 30 * 60
DAY3_MAPS = frozenset(('m12_00_00_00','m18_00_00_00','m19_00_00_00',
                       'm16_00_00_00','m16_10_00_00','m16_11_00_00'))


@dataclass(frozen=True)
class Observation:
    clock_seconds: int
    saved_at: float
    observed_at: float
    play_time_ms: int
    expedition_active: bool | None = None
    map_id: str | None = None
    location_unloaded: bool | None = None


class TimerEngine:
    def __init__(self, clock_rate=72.86):
        self.day = 0
        self.started_at = None
        self.origin = 'Ready'
        self.previous = None
        self.clock_rate = clock_rate
        self.rates = []
        self.auto_start = True
        self.auto_day2 = True
        self.morning_armed = False
        self.transition_pending = False
        self.game_seen = False
        self.window_missing_since = None
        self.suspended_run = None

    def elapsed(self, now):
        return max(0.0, now-self.started_at) if self.started_at is not None else 0.0

    def start(self, day, now, elapsed=0.0, origin='Manual start'):
        if day not in (1,2,3):
            raise ValueError('Unknown day')
        self.day = day
        self.started_at = now-max(0.0, elapsed)
        self.origin = origin
        self.morning_armed = False
        self.transition_pending = False
        self.suspended_run = None

    def stop(self):
        self.day = 0
        self.started_at = None
        self.origin = 'Waiting for expedition...'
        self.morning_armed = False
        self.transition_pending = False
        self.suspended_run = None

    def reset_source(self):
        self.stop()
        self.previous = None
        self.rates.clear()

    def observe_window(self, present, now):
        if present:
            self.game_seen,self.window_missing_since = True,None
        elif self.game_seen:
            if self.window_missing_since is None:self.window_missing_since = now
            elif now-self.window_missing_since>=2:
                self.game_seen = False
                self.reset_source()
                return 'game_window_closed'

    def observe(self, sample, now):
        previous, self.previous = self.previous, sample
        if previous is not None and sample.saved_at<=previous.saved_at:return None
        fresh = 0 <= sample.observed_at-sample.saved_at <= 30
        if fresh and (sample.map_id=='m10_00_00_00' or
                      (sample.expedition_active is False and sample.clock_seconds==MORNING)):
            was_running = self.day!=0
            self.stop()
            self.morning_armed = sample.clock_seconds==MORNING
            return 'auto_lobby' if was_running else None
        if (fresh and sample.map_id in DAY3_MAPS and sample.clock_seconds>=18*3600
                and sample.expedition_active is not False):
            if self.day!=3:
                self.start(3,now,origin='Day 3 identified from saved location')
                return 'auto_day3'
            return None
        if previous is None:
            self.morning_armed = sample.clock_seconds == MORNING
            return None  # Opening the app over an old save must never start a run.
        delta = sample.clock_seconds-previous.clock_seconds
        interval = sample.saved_at-previous.saved_at
        if fresh and self.suspended_run is not None:
            day,elapsed,play_time = self.suspended_run
            if sample.play_time_ms<=play_time:return None
            # Keep the last known day, but exclude time spent outside the
            # character session. Known Bastion and Day 3 saves take priority.
            self.start(day,now,elapsed+(sample.play_time_ms-play_time)/1000,
                       'Resumed from advancing save data · estimated')
            resumed = True
        else:resumed = False
        if (fresh and self.day in (1,2,3) and 1<=interval<=15
                and sample.location_unloaded is True and previous.location_unloaded is True
                and sample.expedition_active is True and previous.expedition_active is True
                and sample.play_time_ms==previous.play_time_ms and delta==0):
            suspended=(self.day,self.elapsed(now),sample.play_time_ms)
            self.stop()
            self.suspended_run=suspended
            return 'save_session_suspended'
        if delta > 0 and interval >= 3:
            rate = delta/interval
            if 40 <= rate <= 110:
                self.rates.append(rate)
                self.rates = self.rates[-7:]
                self.clock_rate = median(self.rates)
        if not fresh:
            self.morning_armed = False
            return None
        if sample.clock_seconds == MORNING:
            self.morning_armed = True
        elif self.morning_armed:
            self.morning_armed = False
            # Both recordings show a stationary 06:30 in the Bastion, then
            # 06:30:01/02 at expedition arrival. Require a new, fresh save and
            # advancing play time, never start from a lone saved clock.
            if (self.auto_start and previous.clock_seconds == MORNING
                    and previous.expedition_active is not True
                    and MORNING < sample.clock_seconds <= MORNING+120
                    and sample.play_time_ms > previous.play_time_ms):
                self.rates.clear()
                self.clock_rate = 72.86
                elapsed = ((sample.clock_seconds-MORNING)/self.clock_rate
                           + sample.observed_at-sample.saved_at)
                self.start(1,now,elapsed,'Automatic start · estimated from save file')
                return 'auto_day1'
        if not self.auto_day2 or self.day != 1:
            return 'save_session_resumed' if resumed else None
        previous_was_evening = previous.clock_seconds >= 18*3600
        new_morning = MORNING <= sample.clock_seconds <= 9*3600
        if previous_was_evening and new_morning and delta <= -8*3600:
            if sample.clock_seconds == MORNING:
                if sample.expedition_active is True:
                    self.start(2,now,sample.observed_at-sample.saved_at,
                               'Day 2 synced from save file · estimated')
                    return 'auto_day2'
                # The Bastion also stores exactly 06:30. Do not silently count it.
                self.transition_pending = True
                self.origin = 'Morning reset · waiting for the next save'
                return 'ambiguous_morning'
            self.transition_pending = False
            age = sample.observed_at-sample.saved_at
            elapsed = (sample.clock_seconds-MORNING)/self.clock_rate + age
            self.start(2, now, elapsed, 'Day 2 synced from save file · estimated')
            return 'auto_day2'
        if self.transition_pending and MORNING < sample.clock_seconds <= 9*3600:
            # A new expedition's opening seconds are handled above. Other
            # unrecorded transitions remain unresolved instead of guessing.
            self.origin = 'Unrecognized transition · waiting for game data'
        return 'save_session_resumed' if resumed else None


def format_time(seconds, signed=False):
    value = max(0, int(seconds))
    minutes, remainder = divmod(value, 60)
    return ('+' if signed else '') + f'{minutes:02}:{remainder:02}'


def milestone_text(elapsed, target):
    if elapsed < target:
        return 'in ' + format_time(ceil(target-elapsed))
    return 'overdue by ' + format_time(elapsed-target)
