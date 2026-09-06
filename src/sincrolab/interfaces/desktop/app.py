"""Desktop process entry point with an optional Qt dependency boundary."""

import sys


def main(argv: list[str] | None = None) -> int:
    """Run the desktop event loop, or explain how to install its optional extra."""
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as error:
        if error.name != "PySide6":
            raise
        print(
            "SincroLab Desktop requires the optional PySide6 dependency. "
            "From the checkout, run: uv sync --locked --extra desktop. "
            'For an installed package, use: pip install "sincrolab[desktop]".',
            file=sys.stderr,
        )
        return 2

    from sincrolab.interfaces.desktop.window import MainWindow

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("SincroLab")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
