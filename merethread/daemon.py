"""
Definitions of daemon-thread types: perpetual threads which are meant
to run for as long as the process is alive.
"""

from .thread import Thread, _ThreadStop


################################################################################

class DaemonThread(Thread):
    """
    An abstract daemon thread class.

    A daemon thread should never stop voluntarily, only when it is requested to stop
    (when the ``stop`` method is called).

    A concrete daemon thread is a subclass of ``DaemonThread``, which typically overrides
    ``_main_iteration``.  It is also possible to override ``_main`` directly (instead of
    ``_main_iteration``), in order to define a custom thread main-loop.

    Using the ``target`` argument is not supported.  The function to run in the daemon
    thread is defined by overriding the ``_main`` method.
    """

    def __init__(self, *, daemon=True, **kwargs):
        super().__init__(
            daemon=daemon,
            target=None, args=(), kwargs={},  # caller must not pass these, raises if passed
            **kwargs
        )
        self._is_premature_exit = False

    ################################################################################
    # abstract daemon implementation methods

    def _main(self):
        """
        The main logic for running the daemon thread.

        As daemon threads are supposed to be perpetual, this method should not exit prematurely,
        i.e. should not return or raise an exception before ``stop`` is called.
        """
        self._main_init()
        try:
            while not self.is_stopping():
                try:
                    self._main_iteration()
                except _ThreadStop:
                    raise
                except Exception as e:
                    self._on_error(e)
        finally:
            self._main_destroy()

    def _main_iteration(self):
        """
        A
        """
        raise NotImplementedError('_main_iteration() not defined for %s' % self.__class__.__name__)

    def stop(self, reason=None):
        """
        Signal the thread should stop executing.
        This method returns immediately. A well-behaved daemon thread exits shortly after the call.

        If this is called before the thread is started, it will exit immediately once started.
        """
        self._request_stop(reason=reason)

    ################################################################################
    # hooks

    def _on_error(self, e):
        """
        A hook for handling an exception raised from ``_main_iteration``.
        Concrete ``DaemonThread`` subclasses can override this method for customized
        error-handling.

        If an exception is raised from this method, the thread will abort.
        """
        self.logger.exception('error', exc_info=e)

    def _on_abort(self, e):
        self.logger.exception('aborted due to an error', exc_info=e)

    def _on_exit(self):
        # A daemon should only exit if requested
        if self.is_stopping():
            return  # ok
        self._is_premature_exit = True
        self._on_premature_exit()
        super()._on_exit()

    def _on_premature_exit(self):
        """
        Daemon threads should not exit prematurely.
        This method serves as a error-handler hook for handling a premature-exit condition.

        When this method is called, ``self.exception`` is set to the exception which caused the
        thread to abort, or if ``self.exception`` is None, it means ``_main`` simply returned
        (prematurely) with no error.

        Concrete ``DaemonThread`` subclasses can override this method for customized
        error-handling.
        """
        if self._stop_reason is None:
            self._stop_reason = 'premature'
        if self.exception is not None:
            self.logger.error('exiting prematurely due to an error')
        else:
            self.logger.error('exiting prematurely')

    def _main_init(self):
        pass

    def _main_destroy(self):
        pass

    ################################################################################
    # other

    def is_stopped_prematurely(self):
        return self._is_premature_exit


class EventLoopThread(DaemonThread):
    """
    A specialized DaemonThread_, customized for the common case of running an event-loop.

    The ``_main_iteration`` method is broken down to three operations:

    - ``_read_next_event`` -- abstract
    - ``_handle_event`` -- abstract
    - ``_on_event_error`` -- can be customized by the subclass

    """

    ################################################################################
    # abstract and customizable methods

    def _read_next_event(self):
        """
        Generate the next event to handle. This method is blocking.

        *Event* is an abstract notion, it can be any object at all (except ``None``).
        The event returned is passed to ``_handle_event``.

        Returning None serves for "yielding" control back to the main-loop.  It then checks
        if the thread should stop, and if not, calls this method again.

        In a well-behaved thread, this method will not block for to long, and will "yield"
        control back to the main loop (by returning None) after a short while.

        :note: This method should not return immediately with None (repeatedly), because that
        will result with a busy-wait loop.

        If this method raises an exception, ``_on_error`` is called to handle it.
        """
        raise NotImplementedError('_read_next_event() not defined for %s' %
                                  self.__class__.__name__)

    def _handle_event(self, event):
        """
        Handle the event.

        If this method raises an exception, ``_on_event_error`` is called to handle it.

        :param event: the event object returned from the last call to ``_read_next_event``.
        """
        raise NotImplementedError('_handle_event() not defined for %s' % self.__class__.__name__)

    def _on_event_error(self, event, e):
        """
        Called when ``_handle_event`` raises an exception.

        This method may be overridden for customized error handling.

        If this method raises an exception, ``_on_error`` is called to handle it.
        """
        self.logger.exception('error handling event: %s', event, exc_info=e)

    ################################################################################
    # abstract event loop implementation (private)

    def _main_iteration(self):
        # read an event:
        event = self._read_next_event()
        if event is None:
            return
        # handle the event:
        try:
            self._handle_event(event)
        except _ThreadStop:
            raise
        except Exception as e:
            self._on_event_error(event, e)


################################################################################
