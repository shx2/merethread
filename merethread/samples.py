"""
Concrete thread types, which are not useful in general.
Meant mainly for demonstrating how to define a variety of thread types.
Some of these are also used for unittesting.
"""

import time
from .thread import Thread
from .daemon import DaemonThread, EventLoopThread
from .task import TaskThread, FunctionThread


################################################################################

SAMPLE_RESULT = 42
SAMPLE_EXCEPTION = RuntimeError('failed intentionally')


################################################################################
# Thread samples

class IdleThread(Thread):
    """ A thread which sleeps indefinitely """

    def _main(self):
        self._sleep()

    def stop(self, reason=None):
        return self._request_stop(reason=reason)


class IdleThreadTARGET(Thread):
    """ Same as `IdleThread`_, but using the ``target`` argument. """

    def __init__(self, **kwargs):
        super().__init__(target=_idle, args=(self,), **kwargs)

    def stop(self, reason=None):
        return self._request_stop(reason=reason)


class NoopThread(Thread):
    """ A thread which does nothing and returns immediately """
    def _main(self):
        return


class NoopThreadTARGET(Thread):
    """ Same as `NoopThread`_, but using the ``target`` argument. """
    def __init__(self, **kwargs):
        super().__init__(target=_noop, **kwargs)


class AbortingThread(Thread):
    """ A thread which aborts immediately """

    EXCEPTION_TYPE = type(SAMPLE_EXCEPTION)

    def _main(self):
        _fail()


class AbortingThreadTARGET(Thread):
    """ Same as `AbortingThread`_, but using the ``target`` argument. """

    EXCEPTION_TYPE = type(SAMPLE_EXCEPTION)

    def __init__(self, **kwargs):
        super().__init__(target=_fail, **kwargs)


################################################################################
# DaemonThread samples

class IdleDaemonThread(DaemonThread):
    """ A daemon thread which sleeps indefinitely """
    def _main_iteration(self):
        self._sleep()


class ReturningDaemonThread(DaemonThread):
    """ A daemon which returns immediately (not a valid behavior for a daemon) """
    def _main(self):
        return


class AbortingDaemonThread(DaemonThread):
    """ A daemon which aborts immediately (not a valid behavior for a daemon) """

    EXCEPTION_TYPE = type(SAMPLE_EXCEPTION)

    def _main(self):
        _fail()


class MetronomeDaemonThread(DaemonThread):
    """ A metronome, printing tick and tock """

    def __init__(self, period=1, **kwargs):
        super().__init__(**kwargs)
        self.period = period
        self.count = 0

    def _main_iteration(self):
        self._sleep(self.period / 2.)
        msg = ['Tick', 'tocK'][self.count % 2]
        self.count += 1
        print(msg)


class MetronomeEventLoopThread(EventLoopThread):
    """ An event-loop based metronome """

    def __init__(self, period=1, **kwargs):
        super().__init__(**kwargs)
        self.period = period
        self.count = 0

    def _read_next_event(self):
        self._sleep(self.period / 2.)
        event = ['Tick', 'tocK'][self.count % 2]
        self.count += 1
        return event

    def _handle_event(self, event):
        print(event)


class FaultyMetronomeEventLoopThread(MetronomeEventLoopThread):
    """ An event-loop based metronome, which sometime fails handling an event """

    def _handle_event(self, event):
        if self.count % 10 == 0:
            raise RuntimeError('glitch')
        return super()._handle_event(event)


################################################################################
# TaskThread samples

class NoopTaskThread(TaskThread):
    """ A task which returns immediately """

    RESULT = SAMPLE_RESULT

    def _main(self):
        return self.RESULT


class IdleTaskThread(TaskThread):
    """ A task which sleeps for a predefined period """

    RESULT = SAMPLE_RESULT

    def __init__(self, period=10, **kwargs):
        super().__init__(**kwargs)
        self.period = period

    def _main(self):
        self._sleep(self.period)
        return self.RESULT


class FailedTaskThread(TaskThread):
    """ A task which raises an exception immediately """

    EXCEPTION_TYPE = type(SAMPLE_EXCEPTION)

    def _main(self):
        _fail()


class SlowTaskThread(TaskThread):
    """ Find a prime number greater than N, very inefficiently """

    def __init__(self, min=20000000, **kwargs):
        super().__init__(**kwargs)
        self.min = min

    def _main(self):
        x = self.min
        while True:
            for d in range(2, x):
                self._stop_if_requested()
                if x % d == 0:
                    break
            else:
                return x
            x += 1


def noop_function_thread():
    """ Same as `NoopTaskThread`_, but implemeted using a `FunctionThread`_ """
    return FunctionThread(_noop_func)


def idle_function_thread(*args, **kwargs):
    """ Same as `IdleTaskThread`_, but implemeted using a `FunctionThread`_ """
    return FunctionThread(_long_func, args=args, kwargs=kwargs)


def failed_function_thread():
    """ Same as `FailedTaskThread`_, but implemeted using a `FunctionThread`_ """
    return FunctionThread(_fail)


################################################################################
# misc

def _noop():
    return


def _noop_func():
    return SAMPLE_RESULT


def _long_func(period=10):
    time.sleep(period)
    return SAMPLE_RESULT


def _fail():
    raise SAMPLE_EXCEPTION


def _idle(thread):
    thread._sleep()


################################################################################
