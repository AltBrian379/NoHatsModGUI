import sys

from PySide6.QtWidgets import QApplication

from nohatsgui import APP_NAME
from nohatsgui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
