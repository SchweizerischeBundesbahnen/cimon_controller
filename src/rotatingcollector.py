__author__ = 'u206123'

# for manual test purposes only, cycle through predefined output values

def create(configuration, key=None):
    return RotatingBuildCollector()

class RotatingBuildCollector():
    type = "build"

    status = ({"request_status" : "ok", "result" : "failure"},
              {"request_status" : "ok", "result" : "unstable"},
              {"request_status" : "ok", "result" : "success"},
              {"request_status" : "ok", "result" : "other"},
              {"request_status" : "ok", "result" : "success"},
              {"request_status" : "error"}, # igonred (if show_error_threshold is 3)
              {"request_status" : "error"}, # igonred (if show_error_threshold is 3)
              {"request_status" : "error"}, # igonred (if show_error_threshold is 3)
              {"request_status" : "error"}, # shown
              {"request_status" : "error"}, # shown
              {"request_status" : "not_found"})

    last_status = -1

    def collect(self):
        self.last_status += 1;
        if self.last_status >= len(self.status):
            self.last_status = 0 # rotate
        return {"imaginary.build.job" : self.status[self.last_status]}

if  __name__ =='__main__':
    col = RotatingBuildCollector()
    for i in range(13):
        print(col.collect())