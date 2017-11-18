__author__ = 'florianseidl'

import logging
from cimon import JobStatus,RequestStatus, Health

# for manual test purposes only, cycle through predefined output values

logger = logging.getLogger(__name__)

default_status = (
    JobStatus(request_status=RequestStatus.OK, result=Health.SICK, active=False),
    JobStatus(request_status=RequestStatus.OK, result=Health.SICK, active=True),
    JobStatus(request_status=RequestStatus.OK, result=Health.UNWELL, active=False),
    JobStatus(request_status=RequestStatus.OK, result=Health.UNWELL, active=True),
    JobStatus(request_status=RequestStatus.OK, result=Health.HEALTHY, active=False),
    JobStatus(request_status=RequestStatus.OK, result=Health.HEALTHY, active=True),
    JobStatus(request_status=RequestStatus.OK, result=Health.OTHER, active=False),
    JobStatus(request_status=RequestStatus.OK, result=Health.OTHER, active=True),
    JobStatus(request_status=RequestStatus.ERROR),  # igonred (if show_error_threshold is 3)
    JobStatus(request_status=RequestStatus.ERROR),  # igonred (if show_error_threshold is 3)
    JobStatus(request_status=RequestStatus.ERROR),  # igonred (if show_error_threshold is 3)
    JobStatus(request_status=RequestStatus.ERROR),  # shown
    JobStatus(request_status=RequestStatus.ERROR),  # shown
    JobStatus(request_status=RequestStatus.NOT_FOUND))

def create(configuration, key=None):
    return RotatingBuildCollector(configuration.get("jobName", "imaginary.build.job"),
                                  configuration.get("status", default_status))

class RotatingBuildCollector():
    last_status = -1

    def __init__(self, job_name, status):
        self.job_name = job_name
        self.status = status

    def collect(self):
        self.last_status += 1
        if self.last_status >= len(self.status):
            self.last_status = 0 # rotate
        logging.info("Imaginary build result: " + str(self.status[self.last_status]))
        return {("rotating", self.job_name) : self.status[self.last_status]}

if  __name__ =='__main__':
    col = RotatingBuildCollector()
    for i in range(13):
        print(col.collect())