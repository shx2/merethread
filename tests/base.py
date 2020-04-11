"""
Common unit-tests definitions for the various test in this package.
"""

import time
import unittest

from concurrent.futures import CancelledError

from merethread import ThreadStatus


################################################################################

class BaseThreadTest(unittest.TestCase):

    SHORT_TIMEOUT = 0.3
    LONG_TIMEOUT = 5
    SHORT_DELAY = 0.1

    ################################################################################
    # utility methods for concrete tests

    def create_thread(self, tcls, *args, **kwargs):
        t = tcls(*args, **kwargs)
        self._threads_created.append(t)
        t.future.add_done_callback(lambda fut: self._callback(t, fut))
        return t

    def _callback(self, t, fut):
        # record what the callback is being reported.
        # this is later checked in the various assert_xxx() methods
        try:
            t.CB_result = fut.result(timeout=0)
        except Exception as e:
            t.CB_exception = e

    def start_thread(self, t, *args, **kwargs):
        self.assert_not_started(t)
        t.start()
        self.wait_for_thread_to_start(t, *args, **kwargs)
        return t

    def wait_for_thread_to_start(self, t, timeout=LONG_TIMEOUT):
        start_time = time.time()
        while True:
            if t.is_started():
                return
            time.sleep(self.SHORT_DELAY)
            if time.time() > start_time + timeout:
                raise RuntimeError('thread not started: %s' % t)

    def assert_not_started(self, t):
        self.assertFalse(t.is_alive())
        self.assertFalse(t.is_started())
        self.assertFalse(t.is_stopping())
        self.assertFalse(t.is_stopped())
        self.assertFalse(t.is_aborted())
        self.assertEqual(t.status(), ThreadStatus.not_started)
        self.assertIsNone(t.exception)
        self.assertFalse(t.future.running())
        self.assertFalse(t.future.done())
        self.assertFalse(hasattr(t, 'CB_result'))
        self.assertFalse(hasattr(t, 'CB_exception'))

    def assert_running(self, t):
        self.assertTrue(t.is_alive())
        self.assertTrue(t.is_started())
        self.assertFalse(t.is_stopping())
        self.assertFalse(t.is_stopped())
        self.assertFalse(t.is_aborted())
        self.assertEqual(t.status(), ThreadStatus.running)
        self.assertIsNone(t.exception)
        self.assertTrue(t.future.running())
        self.assertFalse(t.future.done())
        self.assertFalse(t.future.cancelled())
        self.assertFalse(hasattr(t, 'CB_result'))
        self.assertFalse(hasattr(t, 'CB_exception'))

    def assert_not_running(self, t):
        self.assertFalse(t.is_alive())
        self.assertFalse(t.is_stopping())
        self.assertFalse(t.future.running())

    def assert_stopped(self, t):
        self.assert_not_running(t)
        self.assertTrue(t.is_started())
        self.assertTrue(t.is_stopped())

    def assert_stopped_no_error(self, t):
        self.assert_stopped(t)
        self.assertFalse(t.is_aborted())
        self.assertEqual(t.status(), ThreadStatus.stopped)
        self.assertIsNone(t.exception)
        self.assert_future_success(t)

    def assert_aborted(self, t, exc_type=None, is_cancelled=False):
        self.assert_stopped(t)
        self.assertTrue(t.is_aborted())
        if is_cancelled:
            self.assertEqual(t.status(), ThreadStatus.cancelled)
            self.assertTrue(isinstance(t.exception, CancelledError))
            self.assert_future_cancelled(t)
        else:
            self.assertEqual(t.status(), ThreadStatus.aborted)
            self.assertIsNotNone(t.exception)
            self.assert_future_error(t, exc_type=exc_type)

    def assert_cancelled(self, t, exc_type=None):
        self.assert_aborted(t, exc_type=exc_type, is_cancelled=True)

    def assert_future_success(self, t):
        t.future.result(timeout=0)  # assert no raise
        self.assertTrue(hasattr(t, 'CB_result'))
        self.assertFalse(hasattr(t, 'CB_exception'))

    def assert_future_error(self, t, exc_type=None):
        if exc_type is None:
            exc_type = t.EXCEPTION_TYPE
        self.assertRaises(exc_type, t.future.result, timeout=0)
        self.assertFalse(hasattr(t, 'CB_result'))
        self.assertTrue(isinstance(t.CB_exception, exc_type))

    def assert_future_cancelled(self, t):
        self.assertRaises(CancelledError, t.future.result, timeout=0)
        self.assertFalse(hasattr(t, 'CB_result'))
        self.assertTrue(isinstance(t.CB_exception, CancelledError))

    ################################################################################

    def setUp(self):
        self._threads_created = []

    def tearDown(self):
        for t in self._threads_created:
            if not t.is_alive():
                continue
            # best effort to stop the thread.
            # If this is not enough, can try using the trick in raise_exception() from here:
            # https://www.geeksforgeeks.org/python-different-ways-to-kill-a-thread/
            try:
                t.stop('tearDown')
            except Exception:
                pass
            try:
                t.cancel('tearDown')
            except Exception:
                pass
            t.join()


################################################################################
