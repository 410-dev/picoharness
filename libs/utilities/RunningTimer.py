import time

class RunningTimer:
    def __init__(self):
        self.start_time = time.time()
        self.end_time = 0

        self.elapsed_total_seconds = 0
        self.elapsed_hours = 0
        self.elapsed_minutes = 0
        self.elapsed_seconds = 0

    def finish(self) -> "RunningTimer":
        self.end_time = time.time()
        return self

    def start(self) -> "RunningTimer":
        self.start_time = time.time()
        return self

    def result(self, do_print: bool = False) -> "RunningTimer":
        duration = (time.time() if self.end_time == 0 else self.end_time) - self.start_time
        # Human readable
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)

        if do_print:
            print(f"Program executed for {int(hours):02d}:{int(minutes):02d}:{seconds:05.2f} seconds")

        self.elapsed_total_seconds = duration
        self.elapsed_hours = hours
        self.elapsed_minutes = minutes
        self.elapsed_seconds = seconds

        return self