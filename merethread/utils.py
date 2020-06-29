"""
Potentially useful tools for working with threads.
"""

from . import TaskThread


################################################################################

class ThreadLifeCycleContext:
    """
    A context manager for running a thread (or threads) for as long as the enclosed block runs,
    i.e. starting it when the block starts, and stopping it when it is done.

    Useful for various types of monitoring of block execution, e.g. the thread can periodically
    print memory-consumption while a (long-running) block runs.

    On `__enter__`, the thread is started (if haven't been started before).
    On `__exit__`, the thread is (optionally) stopped, and (optionally) joined.

    To be clear, the threads are oblivious to the code running in the block.
    They run their own code, and the code in the block runs in the original caller thread.
    """

    def __init__(self,
                 *threads,
                 stop=True, join=True, join_timeout=None, raise_on_timeout=True,
                 reraise=True,
                 suppress_keyboard_interrupt=True):
        """
        :param threads: `merethread.Thread`s
        :param stop: whether to stop threads on __exit__
        :param join: whether to join threads on __exit__
        :param join_timeout: timeout to pass to `thread.join()`, if `join=True`
        :param raise_on_timeout: whether to raise a `TimeoutError` if `thread.join()` times out
        :param reraise: whether to reraise an exception causing one of the threads to abort
        :param suppress_keyboard_interrupt: whether to propagate KeyboardInterrupt exception
        """
        self.threads = threads
        self.should_stop = stop
        self.should_join = join
        self.join_timeout = join_timeout
        self.should_raise_on_timeout = raise_on_timeout
        self.should_reraise = reraise
        self.suppress_keyboard_interrupt = suppress_keyboard_interrupt
        self._stopped = False

    def __enter__(self):
        for thread in self.threads:
            if not thread.is_started():
                thread.start()

    def __exit__(self, exc_type, exc_value, tb):

        # note: we always stop in case of KeyboardInterrupt, even if self.should_stop=False
        if self.should_stop or isinstance(exc_value, KeyboardInterrupt):
            self._stop()

        new_exception = None

        if self.should_join:
            interrupt = None
            for thread in reversed(self.threads):
                try:
                    self._join_thread(thread)
                except TimeoutError as e:
                    new_exception = e
                    break
                except KeyboardInterrupt as e:
                    interrupt = e
                    new_exception = e
                    break
                except Exception as e:
                    new_exception = e
                    break

            # handle KeyboardInterrupt raised while joining:
            if interrupt is not None:

                if not self._stopped:
                    # note: we stop in case of KeyboardInterrupt, even if self.should_stop=False
                    self._stop()
                    # now join again, after stopping
                    for thread in reversed(self.threads):
                        try:
                            self._join_thread(thread)
                        except TimeoutError as e:
                            return self._report_exception(exc_value, e)
                        except Exception as e:
                            return self._report_exception(exc_value, e)

                return self._report_exception(exc_value, interrupt)

        return self._report_exception(exc_value, new_exception)

    def _stop(self):
        self._stopped = True
        for thread in reversed(self.threads):
            self._stop_thread(thread)

    def _stop_thread(self, thread):
        if not thread.is_alive():
            return
        reason = '%s.__exit__' % type(self).__name__
        if isinstance(thread, TaskThread):
            thread.cancel(reason=reason)
        else:
            thread.stop(reason=reason)

    def _join_thread(self, thread):
        is_done = thread.join(self.join_timeout)
        if is_done:
            if self.should_reraise:
                self._reraise(thread)
        else:
            if self.should_raise_on_timeout:
                raise TimeoutError(thread)

    def _reraise(self, thread):
        kwargs = {}
        if isinstance(thread, TaskThread):
            kwargs.update(suppress_cancelled=True)
        thread.reraise(**kwargs)

    def _report_exception(self, original_exception, new_exception=None):
        # suppress_keyboard_interrupt if relevant:
        if self.suppress_keyboard_interrupt:
            if isinstance(original_exception, KeyboardInterrupt):
                original_exception = None
            if isinstance(new_exception, KeyboardInterrupt):
                new_exception = None
        # the original exception takes precedence over the new exception
        if original_exception is not None:
            return False  # indicate caller to raise original exception
        elif new_exception is not None:
            # report the new exception
            raise new_exception
        else:
            return True  # no exception


################################################################################
