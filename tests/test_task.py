"""
Unit-tests for TaskThreads.
"""

from .base import BaseThreadTest
from merethread.samples import (
    NoopTaskThread, IdleTaskThread, FailedTaskThread,
    noop_function_thread, idle_function_thread, failed_function_thread,
    SAMPLE_RESULT, SAMPLE_EXCEPTION)


################################################################################

class TaskThreadTest(BaseThreadTest):

    # FunctionThread is not cancellable after starting
    CANCELLABLE_THREADS = [IdleTaskThread]
    LONG_THREADS = CANCELLABLE_THREADS + [idle_function_thread]
    SHORT_THREADS = [
        NoopTaskThread, noop_function_thread,
        FailedTaskThread, failed_function_thread,
    ]

    ################################################################################

    def test_cancel(self):
        for tcls in self.CANCELLABLE_THREADS:
            self._test_cancel(self.create_thread(tcls))

    def _test_cancel(self, t):
        self.start_thread(t)
        self.assert_running(t)
        t.cancel('testing')
        t.join(self.SHORT_DELAY)
        self.assert_cancelled(t)

    def test_cancel_before_start(self):
        for tcls in self.LONG_THREADS + self.SHORT_THREADS:
            self._test_cancel_before_start(self.create_thread(tcls))

    def _test_cancel_before_start(self, t):
        self.assert_not_started(t)
        t.cancel('testing')
        t.start()
        t.join(self.SHORT_TIMEOUT)
        self.assert_cancelled(t)

    def test_not_started(self):
        for tcls in self.LONG_THREADS + self.SHORT_THREADS:
            t = self.create_thread(tcls)
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

    def assert_result_equals(self, t, res):
        self.assertEqual(res, t.result)
        self.assertEqual(res, t.future.result(timeout=0))
        self.assertEqual(res, t.CB_result)
        self.assertFalse(hasattr(t, 'CB_exception'))

################################################################################
