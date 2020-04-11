"""
Unit-tests of the basic merethread.Thread class.
"""

from .base import BaseThreadTest
from merethread.samples import (
    IdleThread, IdleThreadTARGET,
    NoopThread, NoopThreadTARGET,
    AbortingThread, AbortingThreadTARGET)


################################################################################

class ThreadTest(BaseThreadTest):

    LONG_THREADS = [IdleThread, IdleThreadTARGET]
    SHORT_THREADS = [NoopThread, NoopThreadTARGET, AbortingThread, AbortingThreadTARGET]

    def test_not_started(self):
        for tcls in self.LONG_THREADS + self.SHORT_THREADS:
            t = self.create_thread(tcls)
            self.assert_not_started(t)

    def test_immediate_return(self):
        t = self.start_thread(self.create_thread(NoopThread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_stopped_no_error(t)

    def test_immediate_abort(self):
        t = self.start_thread(self.create_thread(AbortingThread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_aborted(t)

################################################################################
