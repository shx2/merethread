"""
Miscellaneous tools used in this package.
"""

import sys
import traceback
import datetime
import cProfile


################################################################################

class Runtime:
    """
    A context-manager which records block-execution start-time and end-time.
    """

    def __init__(self, clock=None):
        if clock is None:
            clock = datetime.datetime
        self.clock = clock
        self.start = None
        self.end = None

    def set_start(self, t=None):
        if t is None:
            t = self.now()
        self.start = t
        self.end = None

    def set_end(self, t=None):
        if not self.is_started:
            raise RuntimeError('not started')
        if t is None:
            t = self.now()
        self.end = t

    @property
    def is_started(self):
        return self.start is not None

    @property
    def is_ended(self):
        return self.end is not None

    @property
    def total(self):
        """ end minus start, as timedetla """
        if self.is_ended:
            return self.end - self.start

    @property
    def total_seconds(self):
        """ same as ``total``, but in seconds """
        dt = self.total
        if dt is not None:
            return dt.total_seconds()

    def now(self):
        return self.clock.now()

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self)

    def __str__(self):
        if not self.is_started:
            return 'not started'
        if not self.is_ended:
            return 'running'
        return 'finished after %s' % self.total

    ################################################################################
    # context manager

    def __enter__(self):
        self.set_start()
        self.end = None
        return self

    def __exit__(self, type, value, tb):
        self.set_end()


################################################################################

def get_currnet_stacktrace(thread):
    """
    Returns a multiline string capturing the current stack-trace of the given thread.

    Based on: https://stackoverflow.com/a/2569696
    """
    cur_frame = sys._current_frames().get(thread.ident)
    if cur_frame is None:
        return None
    code = []
    code.append('\n# Thread: %s(%d)' % (thread.name, thread.ident))
    for filename, lineno, name, line in traceback.extract_stack(cur_frame):
        code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
        if line:
            code.append('  %s' % (line.strip()))
    return '\n'.join(code)


################################################################################

class ProfileContext:
    """
    A context manager for profiling blocks.
    """

    def __init__(self, profiler=None,
                 print_stats=False, print_stats_kwargs=None,
                 dump_to_file=None):
        """
        :param print_stats: if True, will print stats on exit
        :param dump_to_file: if passed, will ``dump_stats`` to this path on exit
        """
        if profiler is None:
            profiler = cProfile.Profile()
        self.profiler = profiler
        self.print_stats = print_stats
        self.print_stats_kwargs = print_stats_kwargs
        self.dump_to_file = dump_to_file

    def __enter__(self):
        self.profiler.enable()

    def __exit__(self, type, value, tb):
        self.profiler.disable()

        if self.print_stats:
            kwargs = self.print_stats_kwargs or {}
            try:
                self.profiler.print_stats(**kwargs)
            except Exception:
                # __exit__ must not raise
                pass

        if self.dump_to_file is not None:
            try:
                self.profiler.dump_stats(self.dump_to_file)
            except Exception:
                # __exit__ must not raise
                pass


################################################################################

class NoopContext:
    """ A context manager which does nothing. """

    def __enter__(self):
        pass

    def __exit__(self, *args, **kwargs):
        return False


################################################################################
