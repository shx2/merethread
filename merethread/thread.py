"""
Definitions of *merethread* ``Thread`` baseclass.
"""

import logging
from enum import Enum
import threading as threading
from concurrent.futures import Future

from .misc import Runtime, ProfileContext, NoopContext, get_currnet_stacktrace


################################################################################
# Misc classes

class _ThreadStop(Exception):
    """ An internal error raised in a thread to signal it should stop executing. """
    pass


class ThreadStatus(Enum):
    not_started = 'no started'
    running = 'running'
    stopping = 'stopping'
    stopped = 'stopped'
    aborted = 'aborted'
    cancelled = 'cancelled'
    stopped_before_starting = 'stopped before starting'


class ThreadFuture(Future):
    """
    A Future_, with minor improvements and adjustments for making it slightly more suitable
    for "encapsulating the asynchronous execution" of a *thread*.

    Notable additions: the ``thread`` attribute, and the ``add_callback``/``add_errback`` methods.
    """

    def __init__(self, thread, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread = thread

    def add_callback(self, fn):
        """
        Same as ``add_done_callback``, but the only invoked in case of success.

        ``fn`` is passed two positional arguments: the thread and the result.
        """

        def cb(fut):
            try:
                result = fut.get_result()
            except Exception:
                # error, so not calling the callback
                pass
            else:
                return fn(fut.thread, result)

        self.add_done_callback(cb)

    def add_errback(self, fn):
        """
        Same as ``add_done_callback``, but only invoked in case of an error.

        If the future was cancelled, ``fn`` will be called with the ``CancelledError`` exception.

        ``fn`` is passed two positional arguments: the thread and the exception.
        """

        def eb(fut):
            try:
                fut.get_result()
                # no error, so not calling the errback
            except Exception as e:
                return fn(fut.thread, e)

        self.add_done_callback(eb)

    def cancel(self):
        raise NotImplementedError(
            'Cancelling a thread is not supported. '
            'Use DaemonThread.stop() or TaskThread.cancel() instead '
            '(e.g. future.thread.cancel()).')


################################################################################
# The MereThread thread baseclass

class Thread(threading.Thread):
    """
    The *merethread* ``Thread`` baseclass.
    This class is merely a subclass of `threading.Thread`_, which adds various useful features and
    capabilities to it.

    In most cases, you wouldn't want to use this class directly, but a subclass
    suitable for your use case, e.g ``DaemonThread``, ``TaskThread``, etc.

    This class adds a few features to threads (see the docs for details):

    - ``exception`` attribute for accessing the exception which caused thread to abort.
    - ``_result`` attribute for accessing the value returned by the ``_main`` method.
    - A `concurrent.futures.Future`_ interface, using the ``future`` attribute.
    - Clean stopping of the thread: this is implemented in this base class, but exposed in
        subclasses. See ``DaemonThread`` and ``TaskThread`` for example.
    - Easily run with a profiler.
    - Easily view the current (live) stack-trace of the thread.
    - ``runtime`` attribute for accessing thread execution start/end times.
    - The ``join`` method returns a bool indicating whether thread has finished.

    :note:
        Unlike usage of the `threading.Thread`_ class, when subclassing ``merethread.Thread`` you
        DO NOT override the ``run`` method.  You should override the ``_main`` method instead.
        This class defines ``run``, and the entry point for custom subclasses is the ``_main``
        method.

    To support stopping, the ``_main`` method should call the ``_stop_if_requested`` or ``_sleep``
    methods often. See the *Well Behaved Threads* section of the docs for more details.
    """

    # Implementation note: to avoid problems related to issue #18808, we avoid accessing
    # the _is_stopped member directly.  Calling is_alive() is a safer option, and is appropriate
    # in most cases.

    Future = ThreadFuture
    Runtime = Runtime
    ProfileContext = ProfileContext

    ################################################################################
    # constructor

    def __init__(self, *,
                 logger=None,
                 profile=False, profile_kwargs=None,
                 **kwargs):
        """
        :param profile: If True, the thread will run with profiling enabled, using ProfileContext_.
        :param profile_kwargs: extra kwargs to pass to the ``ProfileContext``.
        """

        super().__init__(**kwargs)

        if logger is None:
            logger = logging.getLogger('%s' % self.name)
        self.logger = logger

        self._stopping_event = threading.Event()
        self._stop_reason = None

        if profile_kwargs is None:
            profile_kwargs = {}
        self._profiler_ctx = self._get_profiler_ctxmgr(profile, **profile_kwargs)

        # The following are private. subclasses should not set them:
        self.__result = None
        self.__exception = None
        self.__runtime = self.Runtime()
        self.__future = self.Future(self)

    ################################################################################
    # main

    def run(self):
        """
        The basic *merethread* main logic.

        DO NOT OVERRIDE THIS METHOD.  You should override ``_main`` instead.
        """

        with self._profiler_ctx, self.__runtime:

            result = None
            exception = None

            try:

                self.future.set_running_or_notify_cancel()

                # pre-start checks
                if not self._stopping_event.is_set():
                    # starting
                    self._on_enter()
                    # main
                    result = self._main()
                else:
                    # thread stop requested before we got a chance to start running
                    self._handle_stop_before_start()

                return result

            except _ThreadStop as e:
                # stop has been requested
                try:
                    self._on_thread_stop(e)  # may raise or not
                except Exception as e2:
                    exception = e2

            except Exception as e:
                exception = e

            finally:

                # set self.__result and self.__exception
                if exception is not None:
                    self.__exception = exception
                    self._on_abort(self.__exception)
                else:
                    self.__result = result

                # set self.future with the result/exception:
                if not self.future.cancelled():
                    if exception is not None:
                        self.future.set_exception(exception)
                    else:
                        self.future.set_result(result)

                # other cleanups:
                self._on_exit()

    def _main(self):
        """
        Method representing the thread's activity.

        Subclasses should override the ``_main`` method instead of ``run``.
        """
        return super().run()

    ################################################################################
    # stopping

    def _request_stop(self, reason=None):
        """
        Signal the thread it should stop as soon as possible.

        A well-behaved thread will stop shortly after ``_request_stop`` is called.

        Can be called from any thread.
        """
        self.logger.info('%sstop requested (%s)', self._log_prefix, reason)
        self._stop_reason = reason
        self._stopping_event.set()

    def _stop_if_requested(self):
        """
        Raises `_ThreadStop`_ if ``_request_stop`` has already been called.
        """
        self._sleep(0)

    def _sleep(self, timeout=None):
        """
        Sleep for ``timeout`` seconds, or until ``_request_stop`` is called.

        :raise _ThreadStop: if ``_request_stop`` is called while (or prior to) sleeping.
        """
        is_stopping = self._stopping_event.wait(timeout)
        if is_stopping:
            raise _ThreadStop()

    ################################################################################
    # state

    def is_started(self):
        """
        Has this thread been started (whether finished or not)?
        """
        return self._started.is_set()

    def is_stopping(self):
        """
        Is this thread being stopped?

        A thread is in a "stopping" state if self._request_stop() has been called, but the thread
        is still alive.
        """
        return self._stopping_event.is_set() and self.is_alive()

    def is_stopped(self):
        """
        Has this thread already stopped?
        """
        return self.is_started() and not self.is_alive()

    def is_aborted(self):
        """
        Has this thread stopped due to an error?
        """
        return self.__exception is not None and not self.is_alive()

    def status(self):
        """
        A `ThreadStatus`_ representing the current status of the thread.
        """
        stopping = self._stopping_event.is_set()
        if not self.is_started():
            return ThreadStatus.stopped_before_starting if stopping else ThreadStatus.not_started
        elif self.is_alive():
            return ThreadStatus.stopping if stopping else ThreadStatus.running
        elif self.is_aborted():
            return ThreadStatus.aborted
        else:
            assert self.is_stopped()
            return ThreadStatus.stopped

    ################################################################################
    # hooks

    def _on_enter(self):
        """
        A hook which is called when the thread starts executing.

        Will not be called if the thread is requested to stop before it started.

        If an exception is raised, the thread will abort with that exception.
        """
        self.logger.info('%sstarting', self._log_prefix)

    def _on_exit(self):
        """
        A hook which is called as the last thing to do before the thread finishes.

        Called regardless of whether the thread finished successfully or aborted due to
        an error.
        """
        self.logger.info('%sdone', self._log_prefix)

    def _on_abort(self, e):
        """
        A hook for handling (reporting) the case where the thread is aborting due to
        an exception.

        The ``_on_exit`` hook will be called after this.

        No exception should be raised from this method.
        """
        pass

    def _on_thread_stop(self, e):
        """
        A hook which controls what to do when the thread detects it has been requested to stop.

        If an exception is raised, the thread will abort with that exception.
        Else, the thread will exit cleanly.
        """
        self.logger.info('%sstopping', self._log_prefix)

    def _handle_stop_before_start(self):
        """
        A hook which controls what to do when the thread detects it has been requested to stop
        before it started to run.

        If this is called, ``_on_enter`` and ``_main`` are not called.

        If an exception is raised, the thread will abort with that exception.
        Else, the thread will exit cleanly.
        """
        self.logger.info('%snot starting, stop already requested', self._log_prefix)

    ################################################################################
    # profiling, debugging, introspection

    def _get_profiler_ctxmgr(self, profile, **kwargs):
        if profile:
            return self.ProfileContext(**kwargs)
        else:
            return NoopContext()

    @property
    def profiler(self):
        """
        A profiler object which can be used for accessing profiler stats for this thread.

        This is None if profiling has not been enabled (using the ``profile`` flag)
        """
        return getattr(self._profiler_ctx, 'profiler', None)

    @property
    def runtime(self):
        """
        A Runtime_ object capturing thread's start/end times.
        """
        return self.__runtime

    def get_current_stacktrace(self):
        """
        :return: a multiline string capturing the current stack-trace of this thread.
        """
        return get_currnet_stacktrace(self)

    ################################################################################
    # other

    @property
    def future(self):
        """
        A ThreadFuture_ which can be used for adding callbacks (and errbacks) to be
        called when the thread finishes.

        Useful mainly for ``TaskThread``s.

        :note: The thread *cannot* be cancelled using ``t.future.cancel()``.
        """
        return self.__future

    @property
    def result(self):
        """
        If the thread finished with no error, this is the value returned from its ``_main``.
        Else (hasn't finished yet, or aborted), this is None.
        """
        return self.__result

    @property
    def exception(self):
        """
        If the thread aborted, this is the exception which caused it to abort.
        Else (hasn't finished yet, or finished with no error), this is None.
        """
        return self.__exception

    def reraise(self):
        """
        If the thread aborted with an error, raise it in this current (caller) thread.
        """
        if self.__exception is not None:
            raise self.__exception

    def join(self, timeout=None):
        """
        Same as `threading.Thread.join`_, but also returns a flag indicating whether
        the operation completed with no timeout (similar to ``Event.wait``, ``Lock.acquire``,
        etc).

        From the documentation of the baseclass::

            As join() always returns None, you must call isAlive() after join() to decide whether
            a timeout happened -- if the thread is still alive, the join() call timed out.

        This method does this for you, so you don't have to call is_alive().

        :return: False iff returned due to a timeout.
        """
        super().join(timeout)
        return not self.is_alive()

    @property
    def _log_prefix(self):
        return '%s: ' % self.name

    def __repr__(self):
        assert self._initialized, "Thread.__init__() was not called"

        status = self._status_repr()
        if self.is_stopped():
            status += ', %s' % self.runtime
        status = '[%s]' % status

        return '<%s>' % ' '.join(
            str(x) for x in
            [self.__class__.__name__, self.name, self.ident, status]
            if x
        )

    def _status_repr(self):
        status = self.status().value
        if self._stop_reason is not None:
            status += ' (%s)' % self._stop_reason
        return status


################################################################################
