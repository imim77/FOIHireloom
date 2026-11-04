from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol


type ServiceOpener[T] = Callable[[], AbstractAsyncContextManager[T]]


class DatabaseServiceOpener[T](Protocol):
    """DatabaseServiceOpener opens a service with optional persistence for dry runs."""

    def __call__(self, *, with_database: bool = True) -> AbstractAsyncContextManager[T]: ...
