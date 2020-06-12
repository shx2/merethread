==================================
MereThread
==================================

What is MereThread?
=====================

MereThreads are merely python threads (subclasses of ``threading.Thread``), plus various
useful features.

This package also includes thread classes suitable for common use cases
(specifically, ``EventLoopThread`` and ``TaskThread``).


What MereThread isn't?
--------------------------

This isn't an ambitous new approach to multithreading.  Mere threads, plus added features.
No magic is involved.

If you're familiar with working with standard python threads (the ``threading.Thread`` class),
there's almost nothing new to learn before using MereThreads, and benefiting from the
useful features.


Features
==================

- Added attributes:

    - ``Thread.result``: the value "returned" by the thread (e.g. the result of a computation).
    - ``Thread.exception``: the exception which caused the thread to abort.

- ``Future``-interface: A ``concurrent.futures.Future`` interface, using the ``Thread.future`` attribute.

    - Useful mainly for adding callbacks/errbacks to be called when the thread finishes.
    - Also allows you to wait on multiple threads (using
      ``concurrent.futures.wait()`` or ``concurrent.futures.as_completed()`` )

- Clean stopping/cancelling: by calling ``DaemonThread.stop()``, or ``TaskThread.cancel()``.

    - This depends on thread's `well-behaved-ness <#well-behaved-threads>`_.

- Debugging and profiling threads

    - Easily profile a thread.

        - Enable profiling on the thread by passing ``profile=True``.
        - Access profiler data and stats using the ``Thread.profiler`` attribute.

    - Easily view the current (live) stack-trace of the thread, using the
      ``Thread.get_current_stacktrace()`` method.

    - Access thread execution start/end times, using the ``Thread.runtime`` attribute.

- The ``Thread.join()`` method returns a bool indicating whether thread has finished

    - This corrects an annoying inconvenience in the interface of the standard ``Thread`` class.


Thread Classes
==================

This package includes definitions of **abstract thread classes**, suitable for common use cases.

These classes are subclasses of the ``merethread.Thread`` baseclass, and include all the features
listed above.

These are:

- ``DaemonThread``: A thread which is meant to run for as long as the process is alive.

    - Can be signaled to stop (cleanly) by calling its ``DaemonThread.stop()`` method.
    - Exiting prematurely is considered an error, and an appropriate error handler is called, so
      they don't disappear silently.

- ``EventLoopThread``: A specialized ``DaemonThread``, customized for the common case of running
  an `event-loop <https://en.wikipedia.org/wiki/Event_loop>`_.

    - A concrete ``EventLoopThread`` subclass only needs to define how to read the next event, and how
      to handle an event.

- ``TaskThread``: A "temporary" thread which is meant to run a specific task (e.g. compute some value)
  and exit.

    - Can be cancelled (cleanly) by calling its ``TaskThread.cancel()`` method.

- ``ExpiringTaskThread``: A thread which is meant to run for a predefined duration and exit.

- ``FunctionThread``: A specialized ``TaskThread`` which runs a caller-provided ``target`` function
  (similar to the standard ``Thread`` ``target`` arguemnt).

    - This class is provided for convenience.  It is not a well-behaved thread.
    - Cancelling a ``FunctionThread`` can only be done before it starts running.
    - You should prefer subclassing ``TaskThread`` instead of using a ``FunctionThread`` when
      possible.


Well Behaved Threads
======================

In order to support clean stopping/cancelling of threads, the concrete thread subclasses have to adhere
to one basic rule: they have to

    *check* **OFTEN** *if the thread has been signalled to stop/cancel.*

The frequency of the check defines thread's responsiveness to stopping/cancelling.
In other words, a check frequency of at most X seconds means it can take up to X seconds, from the time
stop/cancel is requested, until the thread stops (or, more accurately, until it detects it should stop, and
moves on to its exiting-routine).

How often is **OFTEN**?  That depends on the application, but a good rule of thumb, for most applications,
is that a frequency of 200 millis is often enough, and 2 seconds is not.
Care should also be taken not to check too often (e.g. every 0.1 millis), because that would result in a
busy-wait loop, and wasted CPU time.


Installation
==================

Install using ``pip``::

    % pip install merethread


Other locations
==================

- `MereThread's GitHub page <https://github.com/shx2/merethread>`_
- `MereThread on PyPI <https://pypi.python.org/pypi?:action=display&name=merethread>`_
