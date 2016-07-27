# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = '<your_userid_here>'

# Template for a bulid collector
# copy and add your functionality

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    return MyBuildCollector(configuration)

class MyBuildCollector():
    """"Template for your collecting build status from your own source"""
    type = "build"

    def collect(self):
        """
        :return: A dictionary in the format
            {"<job_name_1>": {"request_status" : "error" | "not_found" | "ok", "result" : "failure" | "unstable" | "other" | "success"},
            "<job_name_2>": {...},
            ...}
        """
        return {}

if  __name__ =='__main__':
    """Smoke Test"""
    col = MyBuildCollector()
    print(col.collect())