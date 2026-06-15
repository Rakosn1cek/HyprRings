# -------------------------------------
# HyprRings - Animation Module
# Author: Lukas Grumlik (Rakosn1cek)
# Version: 0.2.0
# -------------------------------------

import time

class DrawerAnimator:
    def __init__(self, width, speed):
        self.drawer_width = width
        self.drawer_speed_pps = speed
        self.drawer_current_x = -float(width)
        self.drawer_open = False
        self.last_frame_time = time.perf_counter()

    def process(self):
        now = time.perf_counter()
        delta_seconds = now - self.last_frame_time
        self.last_frame_time = now
        
        if delta_seconds <= 0.0 or delta_seconds > 0.1:
            delta_seconds = 1.0 / 60.0
            
        target_x = 0.0 if self.drawer_open else float(-self.drawer_width)
        distance_to_travel = float(self.drawer_speed_pps * delta_seconds)
        
        if self.drawer_current_x < target_x:
            self.drawer_current_x = min(target_x, self.drawer_current_x + distance_to_travel)
        elif self.drawer_current_x > target_x:
            self.drawer_current_x = max(target_x, self.drawer_current_x - distance_to_travel)
            
        return self.drawer_current_x
