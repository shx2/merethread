"""
Unit-tests for TaskThreads.
"""

import time
from datetime import datetime, timedelta

from .base import BaseThreadTest
from merethread.samples import (
    NoopTaskThread, IdleTaskThread, FailedTaskThread,
    NoopExpiringTaskThread, IdleExpiringTaskThread, FailedExpiringTaskThread,
    noop_function_thread, idle_function_thread, failed_function_thread,
    SAMPLE_RESULT, SAMPLE_EXCEPTION)


################################################################################

class TaskThreadTest(BaseThreadTest):

    SHORT_TIMEOUT = BaseThreadTest.SHORT_TIMEOUT * 2
    EXPIRY = SHORT_TIMEOUT / 2

    # FunctionThread is not cancellable after starting
    CANCELLABLE_THREADS = [
        (IdleTaskThread, {}),
        (IdleExpiringTaskThread, {'expiry': EXPIRY}),
    ]
    LONG_THREADS = CANCELLABLE_THREADS + [
        (idle_function_thread, {}),
    ]
    SHORT_THREADS = [
        (NoopTaskThread, {}),
        (NoopExpiringTaskThread, {'expiry': EXPIRY}),
        (noop_function_thread, {}),
        (FailedTaskThread, {}),
        (FailedExpiringTaskThread, {'expiry': EXPIRY}),
        (failed_function_thread, {}),
    ]

    ################################################################################

    def test_cancel(self):
        for tcls, kwargs in self.CANCELLABLE_THREADS:
            self._test_cancel(self.create_thread(tcls, **kwargs))

    def _test_cancel(self, t):
        self.start_thread(t)
        self.assert_running(t)
        t.cancel('testing')
        t.join(self.SHORT_DELAY)
        self.assert_cancelled(t)

    def test_cancel_before_start(self):
        for tcls, kwargs in self.LONG_THREADS + self.SHORT_THREADS:
            self._test_cancel_before_start(self.create_thread(tcls, **kwargs))

    def _test_cancel_before_start(self, t):
        self.assert_not_started(t)
        t.cancel('testing')
        t.start()
        t.join(self.SHORT_TIMEOUT)
        self.assert_cancelled(t)

    def test_not_started(self):
        for tcls, kwargs in self.LONG_THREADS + self.SHORT_THREADS:
            t = self.create_thread(tcls, **kwargs)
            self.assert_not_started(t)

    def test_immediate_return(self):
        t = self.start_thread(self.create_thread(NoopTaskThread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_stopped_no_error(t)
        self.assert_result_equals(t, t.RESULT)

    def test_immediate_return_function(self):
        t = self.start_thread(self.create_thread(noop_function_thread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_stopped_no_error(t)
        self.assert_result_equals(t, SAMPLE_RESULT)

    def test_immediate_abort(self):
        t = self.start_thread(self.create_thread(FailedTaskThread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_aborted(t)

    def test_immediate_abort_function(self):
        t = self.start_thread(self.create_thread(failed_function_thread))
        t.join(self.SHORT_TIMEOUT)
        self.assert_aborted(t, exc_type=type(SAMPLE_EXCEPTION))

    ################################################################################
    # expiry tests

    def test_expires_absolute(self):
        self._test_expires(datetime.now() + timedelta(seconds=self.EXPIRY))

    def test_expires_seconds(self):
        self._test_expires(self.EXPIRY)

    def test_expires_timedetla(self):
        self._test_expires(timedelta(seconds=self.EXPIRY))

    def test_expires_immediate_absolute(self):
        self._test_expires(datetime.now(), immediate=True)

    def test_expires_immediate_seconds(self):
        self._test_expires(0, immediate=True)

    def test_expires_immediate_timedetla(self):
        self._test_expires(timedelta(seconds=0), immediate=True)

    def test_expires_negative_absolute(self):
        self._test_expires(datetime.now() - timedelta(seconds=100), immediate=True)

    def test_expires_negative_seconds(self):
        self._test_expires(-100, immediate=True)

    def test_expires_negative_timedetla(self):
        self._test_expires(timedelta(seconds=-100), immediate=True)

    def _test_expires(self, expiry, immediate=False):
        t = self.start_thread(self.create_thread(IdleExpiringTaskThread, expiry=expiry))
        time.sleep(self.SHORT_DELAY)
        if not immediate:
            self.assert_running(t)
            t.join(self.SHORT_TIMEOUT)
        self.assert_expired(t)

    def assert_expired(self, t):
        self.assert_stopped_no_error(t)
        self.assertTrue(t.is_expired())

    def assert_not_expired(self, t):
        self.assert_stopped_no_error(t)
        self.assertFalse(t.is_expired())

    ################################################################################

    def assert_result_equals(self, t, res):
        self.assertEqual(res, t.result)
        self.assertEqual(res, t.future.result(timeout=0))
        self.assertEqual(res, t.CB_result)
        self.assertFalse(hasattr(t, 'CB_exception'))

################################################################################
