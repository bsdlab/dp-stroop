import time

from dareplane_utils.general.event_loop import EventLoop
from pyglet.window import BaseWindow


class MyEventLoop(EventLoop):
    def __init__(self, window: BaseWindow, dt_s: float = 0.001, frame_rate: int = 60):
        super().__init__(dt_s=dt_s)
        self.window = window
        self.dt_frames = 1 / frame_rate
        self.last_frame_update = time.perf_counter()

        self.add_callback(self.frame_update)

    def frame_update(self, ctx):
        """Trigger frame updates at a different rate than checking the main loop"""
        now = time.perf_counter()
        if now - self.last_frame_update > self.dt_frames:
            self.window.dispatch_events()
            self.window.dispatch_event("on_draw")
            self.window.flip()
            self.last_frame_update = time.perf_counter()
