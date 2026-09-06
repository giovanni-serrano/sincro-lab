"""Run an immutable controller job outside the Qt event loop."""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class OperationWorker(QThread):
    succeeded = Signal(object)
    rejected = Signal(object)

    def __init__(self, job: Callable[[], object], parent=None) -> None:
        super().__init__(parent)
        self.job = job

    def run(self) -> None:
        try:
            result = self.job()
        except (ValueError, TypeError, ArithmeticError, RuntimeError) as error:
            # Input errors, numerical failures and application invariant failures
            # retain their exception for inspection, never becoming a status.
            self.rejected.emit(error)
        else:
            self.succeeded.emit(result)
