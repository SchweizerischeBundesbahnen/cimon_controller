# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

import random
from datetime import datetime

# for manual test purposes only
# creates random build results

def create(configuration, key=None):
    return RandomBuildCollector()

def select_randval(**key_percentage):
    if sum(key_percentage.values()) != 100:
        raise Exception("Sum of percentages was %s, expected 100" % sum(key_percentage.values()))
    rand = random.randint(0, 99)
    x = 0
    for key, val in key_percentage.items():
        x += val
        if rand < x:
            return key

class RandomBuildCollector():
    """returns random states for predefined buils"""
    type = "build"
    builds = ("foo", "bar", "any.thing", "what.ever", "some.unknown.build")

    def collect(self):
        status = {}
        for build in self.builds:
            status[build] = self.__random_status__()
        return status

    def __random_status__(self):
        return {"request_status" : select_randval(ok=90, not_found=7,failed=3),
                "building" : random.randint(0, 99) < 5,
                "result" : select_randval(success=75, failed=15, unstable=5, other=5),
                "number" : random.randint(0, 999),
                "timestamp" : datetime.now() }

if  __name__ =='__main__':
    print(RandomBuildCollector().collect())