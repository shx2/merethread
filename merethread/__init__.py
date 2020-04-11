"""
The ``merethread`` package, providing thread classes with various useful features, as well as
customized ``threading.Thread`` subclasses suitable for the most common cases of using threads.

For details, see the docs.
"""

from .thread import Thread, ThreadStatus
from .daemon import DaemonThread, EventLoopThread
from .task import TaskThread, FunctionThread

Thread, ThreadStatus, DaemonThread, EventLoopThread, TaskThread, FunctionThread  # pyflakes
