"""
Unit-tests for TaskThreads.
"""

import time
from datetime import datetime, timedelta

from .base import BaseThreadTest
from merethread.samples import (
    NoopTaskThread, IdleTaskThread, FailedTaskThread,
    NoopLimitedTimeTaskThread, IdleLimitedTimeTaskThread, FailedLimitedTimeTaskThread,
    NoopTimeoutTaskThread, IdleTimeoutTaskThread, FailedTimeoutTaskThread,
    noop_function_thread, idle_function_thread, failed_function_thread,
    SAMPLE_RESULT, SAMPLE_EXCEPTION)


################################################################################

class TaskThreadTest(BaseThreadTest):

    SHORT_TIMEOUT = BaseThreadTest.SHORT_TIMEOUT * 2
    EXPIRY = SHORT_TIMEOUT / 2

    # FunctionThread is not cancellable after starting
    CANCELLABLE_THREADS = [
        (IdleTaskThread, {}),
        (IdleLimitedTimeTaskThread, {'expiry': EXPIRY}),
        (IdleTimeoutTaskThread, {'expiry': EXPIRY}),
    ]
    LONG_THREADS = CANCELLABLE_THREADS + [
        (idle_function_thread, {}),
    ]
    SHORT_THREADS = [
        (NoopTaskThread, {}),
        (NoopLimitedTimeTaskThread, {'expiry': EXPIRY}),
        (NoopTimeoutTaskThread, {'expiry': EXPIRY}),
        (noop_function_thread, {}),
        (FailedTaskThread, {}),
        (FailedLimitedTimeTaskThread, {'expiry': EXPIRY}),
        (FailedTimeoutTaskThread, {'expiry': EXPIRY}),
        (failed_function_thread, {}),
    ]
    IDLE_EXPIRY_THREADS = [IdleLimitedTimeTaskThread, IdleTimeoutTaskThread]

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
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, datetime.now() + timedelta(seconds=self.EXPIRY))

    def test_expires_seconds(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, self.EXPIRY)

    def test_expires_timedetla(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, timedelta(seconds=self.EXPIRY))

    def test_expires_immediate_absolute(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, datetime.now(), immediate=True)

    def test_expires_immediate_seconds(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, 0, immediate=True)

    def test_expires_immediate_timedetla(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, timedelta(seconds=0), immediate=True)

    def test_expires_negative_absolute(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, datetime.now() - timedelta(seconds=100), immediate=True)

    def test_expires_negative_seconds(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, -100, immediate=True)

    def test_expires_negative_timedetla(self):
        for thread_cls in self.IDLE_EXPIRY_THREADS:
            self._test_expires(thread_cls, timedelta(seconds=-100), immediate=True)

    def _test_expires(self, thread_cls, expiry, immediate=False):
        t = self.start_thread(self.create_thread(thread_cls, expiry=expiry))
        time.sleep(self.SHORT_DELAY)
        if not immediate:
            self.assert_running(t)
            t.join(self.SHORT_TIMEOUT)
        self.assert_expired(t)

    def assert_expired(self, t):
        self.assertTrue(t.is_expired())
        if isinstance(t, IdleTimeoutTaskThread):
            # TimeoutError upon expiry
            self.assert_aborted(t, TimeoutError)
        else:
            # no error upon expiry
            self.assert_stopped_no_error(t)

    ################################################################################

    def assert_result_equals(self, t, res):
        self.assertEqual(res, t.result)
        self.assertEqual(res, t.future.result(timeout=0))
        self.assertEqual(res, t.CB_result)
        self.assertFalse(hasattr(t, 'CB_exception'))

################################################################################
