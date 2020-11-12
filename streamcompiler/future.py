from __future__ import annotations

from typing import Callable, Generic, List, Optional, TypeVar
from gi.repository import GLib

T = TypeVar('T')
V = TypeVar('V')


def run_soon(fun: Callable) -> None:
    def run():
        fun()
        return False

    GLib.idle_add(run)


def then(next: Future[V], fun: Callable[[T], V]) -> Callable[[Future[T]], None]:
    def _then(fut: Future[T]) -> None:
        exc = fut.exception()
        if exc:
            next.set_exception(exc)
            return
        next.set_result(fun(fut.result()))
    return _then


class Future(Generic[T]):
    __sentinel = object()

    _result: T
    _exception: Exception
    _callback: Callable

    def __init__(self) -> None:
        self._callback = None  # type: ignore

    def result(self) -> T:
        exception = getattr(self, '_exception', self.__sentinel)
        if exception is not self.__sentinel:
            raise exception
        result = getattr(self, '_result', self.__sentinel)
        if result is not self.__sentinel:
            return result
        raise RuntimeError("Result is not ready")

    def set_result(self, result: T) -> None:
        self._result = result
        if self._callback:
            run_soon(lambda: self._callback(self))

    def set_exception(self, exception: Exception) -> None:
        self._exception = exception
        if self._callback:
            run_soon(lambda: self._callback(self))

    def exception(self) -> Optional[Exception]:
        return getattr(self, '_exception', None)

    def done(self) -> bool:
        return hasattr(self, '_result') or hasattr(self, '_exception')

    def cancelled(self) -> bool:
        return False

    def add_done_callback(self, callback: Callable[[Future[T]], None]) -> None:
        self._callback = callback  # type: ignore
        if self.done():
            run_soon(lambda: self._callback(self))

    def then(self, callback: Callable[[T], V]) -> Future[V]:
        future: Future[V] = Future()
        self.add_done_callback(then(future, callback))
        return future

    @classmethod
    def gather(cls, futures: List[Future[T]]) -> Future[List[T]]:
        def complete(fut) -> None:
            if future.done():
                return

            exc = fut.exception()
            if exc:
                future.set_exception(exc)
                return

            if all(f.done() for f in futures):
                try:
                    result = [f.result() for f in futures]
                except Exception as e:
                    future.set_exception(e)
                else:
                    future.set_result(result)

        future: Future[List[T]] = Future()
        for fut in futures:
            fut.add_done_callback(complete)

        return future
