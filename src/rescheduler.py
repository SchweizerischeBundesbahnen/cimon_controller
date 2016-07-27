# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from threading import Timer, Lock
from time import sleep

# Rescheduler, mainly stolen from the internet: http://stackoverflow.com/questions/2398661/schedule-a-repeating-event-in-python-3
# is actually a total overkill, for the build monitor a simple sleep() would be sufficient, but it is a bit cleaner this way.
class ReScheduler:
    """
    Implmeents the main loop of the cimon by re-scheduling the run in the given interval
    """

    def __init__(self, method, interval_sec):
        self.__lock= Lock()
        self.__timer = None
        self.__stopped = True
        self.__method = method
        self.__interval_sec = interval_sec

    def run(self):
        interval_override_sec = self.__method()
        self.__lock.acquire()
        if not self.__stopped:
            self.__timer = Timer(interval_override_sec if interval_override_sec else self.__interval_sec, self.run, ())
            self.__timer.start()
        self.__lock.release()

    def start(self):
        self.__lock.acquire()
        if self.__stopped:
            self.__stopped = False
            self.__lock.release()
            self.run()
        else:
            self.__lock.release()
        return self

    def stop(self):
        self.__lock.acquire()
        self.__stopped = True
        if self.__timer:
            self.__timer.cancel()
            self.__timer = None
        self.__lock.release()

def foo():
    print("bar");

if  __name__ =='__main__':
    """smoke test"""
    rs = ReScheduler(foo, 1)
    rs.start()
    sleep(3)
    rs.stop()
