"""
Unit-tests for DaemonThreads.
"""

from .base import BaseThreadTest
from merethread.samples import (
    IdleDaemonThread,
    MetronomeDaemonThread, MetronomeEventLoopThread, FaultyMetronomeEventLoopThread,
    ReturningDaemonThread, AbortingDaemonThread)


################################################################################

METRONOME_KWARGS = {'period': BaseThreadTest.SHORT_DELAY / 100}


################################################################################

class _BaseDaemonThreadTest(BaseThreadTest):

    VALID_DAEMON_THREADS = [
        (IdleDaemonThread, {}),
        (MetronomeDaemonThread, METRONOME_KWARGS),
    ]
    INVALID_DAEMON_THREADS = [
        (ReturningDaemonThread, {}),
        (AbortingDaemonThread, {}),
    ]

    def test_stop(self):
        for tcls, kwargs in self.VALID_DAEMON_THREADS:
            self._test_stop(self.create_thread(tcls, **kwargs))

    def _test_stop(self, t):
        self.start_thread(t)
        self.assert_running(t)
        t.stop('testing')
        t.join(self.SHORT_DELAY)
        self.assert_stopped_no_error(t)

    def test_stop_before_start(self):
        for tcls, kwargs in self.VALID_DAEMON_THREADS + self.INVALID_DAEMON_THREADS:
            self._test_stop_before_start(self.create_thread(tcls, **kwargs))

    def _test_stop_before_start(self, t):
        self.assert_not_started(t)
        t.stop('testing')
        t.start()
        t.join(self.SHORT_TIMEOUT)
        self.assert_stopped_no_error(t)

    def test_not_started(self):
        for tcls, kwargs in self.VALID_DAEMON_THREADS + self.INVALID_DAEMON_THREADS:
            t = self.create_thread(tcls, **kwargs)
            self.assert_not_started(t)


class DaemonThreadTest(_BaseDaemonThreadTest):

    def test_immediate_return(self):
        t = self.start_thread(self.create_thread(ReturningDaemonThread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_stopped_no_error(t)

    def test_immediate_abort(self):
        t = self.start_thread(self.create_thread(AbortingDaemonThread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_aborted(t)


class EventLoopThreadTest(_BaseDaemonThreadTest):

    VALID_DAEMON_THREADS = [
        (MetronomeEventLoopThread, METRONOME_KWARGS),
        (FaultyMetronomeEventLoopThread, METRONOME_KWARGS),
    ]


################################################################################
