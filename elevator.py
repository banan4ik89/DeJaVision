import math
import time

class Elevator:
    def __init__(self, player_angle, on_lift_complete=None):
        self.active = False
        self.start_time = 0.0
        self.from_angle = player_angle
        self.target_angle = player_angle + math.pi
        self.close_t = 0.0
        self.transition_to_next = False
        self.trigger_x = None
        self.trigger_y = None
        self.ELEV_ROT_DUR = 1.0
        self.ELEV_DOOR_CLOSE_DUR = 2.0
        self.ELEV_DOOR_HOLD_DUR = 2.0
        self.ELEV_SHAKE_DUR = 2.0
        self.ELEV_TOTAL_DUR = self.ELEV_DOOR_CLOSE_DUR + self.ELEV_DOOR_HOLD_DUR + self.ELEV_SHAKE_DUR
        self.on_lift_complete = on_lift_complete

    def start(self, player_angle, trigger_x=None, trigger_y=None):
        self.active = True
        self.start_time = time.time()
        self.from_angle = player_angle
        self.target_angle = player_angle + math.pi
        self.close_t = 0.0
        self.trigger_x = trigger_x
        self.trigger_y = trigger_y
        self.transition_to_next = False

    def update(self, player_angle):
        if not self.active:
            return player_angle, 0.0, False
        elapsed = time.time() - self.start_time
        # Camera rotation
        if elapsed < self.ELEV_ROT_DUR:
            ratio = elapsed / self.ELEV_ROT_DUR
            new_angle = self.from_angle + math.pi * (1.0 - (1.0 - ratio) ** 3)
        else:
            new_angle = self.target_angle
        # Door closing
        self.close_t = min(1.0, elapsed / self.ELEV_DOOR_CLOSE_DUR)
        # Complete
        if elapsed >= self.ELEV_TOTAL_DUR:
            if self.on_lift_complete:
                self.on_lift_complete()
            self.transition_to_next = True
        return new_angle, self.close_t, self.transition_to_next

    def stop(self):
        self.active = False
        self.transition_to_next = False
