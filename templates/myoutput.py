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
        Status is a dict with key tuple (collector, job name) and value JobStatus,
        for instance { (<collector1>, <job_name_1>) : <JobStatus Object>,
                       (<collector1>, <job_name_2>) : <JobStatus Object>}
        """
        pass

if  __name__ =='__main__':
    MyOutput().on_update({})