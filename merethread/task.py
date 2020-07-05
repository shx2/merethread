"""
Definitions of task-thread types: temporary threads which are meant
to perform a single task.
"""

import datetime
from concurrent.futures import CancelledError
from .thread import Thread, ThreadStatus, _ThreadStop


################################################################################

class TaskThread(Thread):
    """
    A thread which is meant to be temporary: perform a certain task and finish.

    The task can be cancelled by calling the ``cancel`` method.  When a ``TaskThread`` is
    cancelled successfully, it aborts with a `CancelledError`_.

    When the task completes, the ``result`` attribute is set with the value returned.

    :note:
        in order to be well behaved, the task should call ``_stop_if_requested`` or ``_sleep``
        often enough.
    """

    def cancel(self, reason=None):
        """
        Signal the task should be cancelled, and the thread should abort execution.

        This method returns immediately. A well-behaved daemon thread aborts shortly after
        the call, with a `CancelledError`_ (unless already done).

        If this is called before the thread is started, it will abort immediately once started
        (with a `CancelledError`_).
        """
        if self.is_stopped() or self._stopping_event.is_set():
            return
        if reason is None:
            reason = 'cancelled'
        self._request_stop(reason=reason)

    def is_cancelled(self):
        """
        Has this thread stopped due cancelling?
        """
        return self.is_stopped() and self._stopping_event.is_set()

    def _on_abort(self, e):
        if isinstance(e, CancelledError):
            self.logger.info('task cancelled')
        else:
            self.logger.info('aborted due to an error: %s', e)

    def _on_thread_stop(self, e):
        super()._on_thread_stop(e)
        raise CancelledError() from e  # raise to invoke thread-abort logic

    def _handle_stop_before_start(self):
        super()._handle_stop_before_start()
        raise _ThreadStop()  # raise to invoke self._on_thread_stop

    def status(self):
        """ A string representing the current state of the thread. """
        if self.is_cancelled():
            return ThreadStatus.cancelled
        return super().status()

    def _status_repr(self):
        # return "cancelled" instead of "cancelled (cancelled)"
        status = self.status().value
        if status == str(self._stop_reason):
            return status
        return super()._status_repr()

    def reraise(self, suppress_cancelled=False):
        """
        If the thread aborted with an error, raise it in this current (caller) thread.
        :param suppress_cancelled: if thread aborted due to cancelling, will not raise.
        """
        try:
            super().reraise()
        except CancelledError:
            if not suppress_cancelled:
                raise


class _ExpiringTaskThread(TaskThread):
    """
    An abstract thread to run a task with a predefined expiry.
    When expires, the thread exits gracefully.

    ``expiry`` can be:

     - int/float: number of seconds since thread is started
     - datetime.timedelta: time since thread is started
     - datetime.datetime: absolute expiration time

    """

    class _Expired(_ThreadStop):
        """ An internal error raised to signal it has expired and should stop executing. """
        pass

    def __init__(self, *, expiry, **kwargs):
        super().__init__(**kwargs)

        self._expiry_raw = expiry
        self._expiry = None
        self._expired = False

        # If we got an invalid expiry, report it early:
        self._calc_expiry(self._expiry_raw)

    def _on_enter(self):
        # setting expiry when starting

        super()._on_enter()
        # set expiry:
        self._expiry = self._calc_expiry(self._expiry_raw)
        # check if already expired:
        self._check_expiry()

    def _sleep(self, timeout):
        # enforcing expiry when sleeping

        # check if already expired:
        self._check_expiry()
        # modify timeout so we don't sleep beyond expiry:
        expire_after_sleep = False
        max_timeout = (self._expiry - self._now()).total_seconds()
        if timeout > max_timeout:
            timeout = max(0, max_timeout)
            expire_after_sleep = True
        # sleep:
        super()._sleep(timeout)
        # check if expired after sleeping:
        if expire_after_sleep:
            raise self._Expired()
        self._check_expiry()  # just in case

    def _on_thread_stop(self, e):
        # handle exit-on-expiry

        if isinstance(e, self._Expired):
            # expired -- not an error condition, so suppress error
            self._expired = True
            return self._on_expiry()
        return super()._on_thread_stop(e)

    def _check_expiry(self):
        if self._now() >= self._expiry:
            raise self._Expired()

    def _calc_expiry(self, expiry_raw):
        if isinstance(expiry_raw, datetime.datetime):
            # this is already the expiration time
            return expiry_raw
        elif isinstance(expiry_raw, datetime.timedelta):
            # delta relative to now
            return self._now() + expiry_raw
        elif isinstance(expiry_raw, (int, float)):
            # number of seconds, relative to now
            return self._now() + datetime.timedelta(seconds=expiry_raw)
        else:
            raise TypeError('Invalid expiry: %r' % expiry_raw)

    def is_expired(self):
        return self._expired

    def _on_expiry(self):
        """
        A hook which controls what to do when the thread expires.
        The value returned will be used as task's result.
        """
        raise NotImplementedError


class LimitedTimeTaskThread(_ExpiringTaskThread):
    """
    A `TaskThread` which runs for a predefined period of time, and then finishes
    successfully.
    """

    def _on_expiry(self):
        # finish successfully upon expiry:
        return None


class TimeoutTaskThread(_ExpiringTaskThread):
    """
    A `TaskThread` which runs for no longer than a given timeout.
    When it times out, it aborts with `TimeoutError` exception.
    """

    def _on_expiry(self):
        # abort with a TimeoutError upon expiry:
        raise TimeoutError()

    def is_timed_out(self):
        return self.is_expired()


################################################################################

class FunctionThread(TaskThread):
    """
    A thread for running a given function, passed as the ``target`` argument.

    This class is provided for convenience.  It is not a well-behaved thread,
    as it doesn't support cancelling the task (it only supports cancelling before the
    thread is started).

    It is recommended to use `TaskThread`_ instead, i.e. defining a subclass of
    ``TaskThread`` which performs the task well-behaved-ly.
    """

    def __init__(self, target, *, name=None, **kwargs):
        if name is None:
            try:
                name = target.__name__
            except Exception:
                name = str(target)
        super().__init__(target=target, name=name, **kwargs)

    def _main(self):
        try:
            return self._target(*self._args, **self._kwargs)
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs

    def cancel(self, reason=None):
        if self.is_alive():
            raise RuntimeError('FunctionThread is already running and cannot be cancelled')
        return super().cancel(reason=reason)


################################################################################
