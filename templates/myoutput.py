__author__ = 'florianseidl'
# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = '<your_userid_here>'

# Template for an output. For ampel type output with 3 or less lights or signals, use myampeloutput template instead.
# copy and add your functionality

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    return MyOutput()

class MyOutput():
    """Template for your own output device."""

    def on_update(self, status):
        """Display the given status.
        Status is a dict of status type, for instance { 'build' : {"<job_name_1>": {"request_status" : "error" | "not_found" | "ok", "result" : "failure" | "unstable" | "other" | "success"},
                                                                    "<job_name_2>": {...},
                                                                    ...}
                                                       }
        """
        pass

if  __name__ =='__main__':
    MyOutput().on_update({})