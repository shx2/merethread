"""
Definitions of task-thread types: temporary threads which are meant
to perform a single task.
"""

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
