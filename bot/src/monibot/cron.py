import threading
import queue
import logging
log = logging.getLogger(__name__)


class CronError(Exception):
    pass


class Cron(threading.Thread):
    def __init__(
        self,
        func,
        args=(),
        kwargs={},
        interval_sec=1,
        queue=None,
        command=None
    ):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.interval = interval_sec
        self.queue = queue
        self.command = command
        self.event = threading.Event()
        super(Cron, self).__init__()

    def run(self):
        log.debug(f"start thread({self.func.__name__})")
        while True:
            log.debug(f"call '{self.func.__name__}'")
            ret = self.func(*self.args, **self.kwargs)
            if self.queue and ret:
                log.debug(self.queue)
                self.queue.put_nowait(ret)
            if self.command and ret:
                self.command.message = ret
                self.command.respond()

            if self.event.wait(self.interval):
                break

    def abort(self):
        log.debug(f"aborted thread({self.func.__name__})")
        self.event.set()


def main():
    from datetime import datetime

    def sensor(where, what, unit=''):
        dt = datetime.now()
        mes = (f"{what} in {where} is 10.0 {unit} at {dt}")
        return mes

    crons = []
    q = queue.Queue()
    crons.append(
        Cron(
            sensor,
            args=("living", "humidity"),
            kwargs={'unit': '%'},
            interval_sec=2,
            queue=q
        )
    )
    crons.append(
        Cron(
            sensor,
            args=("living", "temperature"),
            kwargs={'unit': '°C'},
            interval_sec=5,
            queue=q
        )
    )
    for c in crons:
        c.start()
    for i in range(10):
        print(i, q.get())
    print("wait aboting...")
    for c in crons:
        c.abort()
        c.join()
    print("done")


if __name__ == "__main__":
    main()
