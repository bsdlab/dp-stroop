import time

import pyglet
from dareplane_utils.general.event_loop import EventLoop

from stroop_task.utils.logging import logger


class MyEventLoop(EventLoop):
    def __init__(
        self,
        window: pyglet.window.BaseWindow,
        dt_s: float = 0.001,
        frame_rate: int = 65,
    ):
        super().__init__(dt_s=dt_s)
        self.window = window
        self.dt_frames = 1 / frame_rate
        self.last_frame_update = time.perf_counter()

        # Frame update only at frame_rate
        self.add_callback(self.frame_update)
        self.add_callback(self.dispatch_events)

        def stop_event_handler(symbol, modifiers):
            """Additional stop handler -> to interrupt the custom event loop"""
            match symbol:
                case pyglet.window.key.ESCAPE:
                    self.stop_event.set()

        self.window.push_handlers(on_key_press=stop_event_handler)

    def frame_update(self, ctx):
        """Trigger frame updates at a different rate than checking the main loop"""
        now = time.perf_counter()
        # logger.debug("Checking for updates")
        if now - self.last_frame_update > self.dt_frames:
            # logger.debug("Updating frame")
            self.window.switch_to()
            self.window.dispatch_events()
            self.window.dispatch_event("on_draw")
            self.window.flip()
            self.last_frame_update = time.perf_counter()

    def dispatch_events(self, ctx):
        """Wrapper to catch the unused ctx"""
        self.window.dispatch_events()
