__author__ = 'florianseidl'

import logging

# for manual test purposes only, cycle through predefined output values

logger = logging.getLogger(__name__)

def create(configuration, key=None):
    return RotatingBuildCollector()

class RotatingBuildCollector():
    type = "build"

    status = ({"request_status" : "ok", "result" : "failure", "building" : False },
              {"request_status" : "ok", "result" : "failure", "building" : True },
              {"request_status" : "ok", "result" : "unstable", "building" : False },
              {"request_status" : "ok", "result" : "unstable", "building" : True },
              {"request_status" : "ok", "result" : "success", "building" : False },
              {"request_status" : "ok", "result" : "success", "building" : True },
              {"request_status" : "ok", "result" : "other", "building" : False },
              {"request_status" : "ok", "result" : "other", "building" : True },
              {"request_status" : "error"}, # igonred (if show_error_threshold is 3)
              {"request_status" : "error"}, # igonred (if show_error_threshold is 3)
              {"request_status" : "error"}, # igonred (if show_error_threshold is 3)
              {"request_status" : "error"}, # shown
              {"request_status" : "error"}, # shown
              {"request_status" : "not_found"})

    last_status = -1

    def collect(self):
        self.last_status += 1
        if self.last_status >= len(self.status):
            self.last_status = 0 # rotate
        logging.info("Imaginary build result: " + str(self.status[self.last_status]))
        return {"imaginary.build.job" : self.status[self.last_status]}

if  __name__ =='__main__':
    col = RotatingBuildCollector()
    for i in range(13):
        print(col.collect())