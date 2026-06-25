import time

class RunningTimer:
    def __init__(self):
        self.start_time = time.time()
        self.end_time = 0

    def finish(self):
        self.end_time = time.time()

    def start(self):
        self.start_time = time.time()

    def result(self):
        duration = time.time() - self.start_time
        # Human readable
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"Program executed for {int(hours):02d}:{int(minutes):02d}:{seconds:05.2f} seconds")
