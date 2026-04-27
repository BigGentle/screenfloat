import json
import os
import sys
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication
from float_window import FloatWindow


def _data_paths():
    if getattr(sys, "frozen", False):
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    return base, os.path.join(base, "windows.json")


DATA_DIR, DATA_FILE = _data_paths()

windows = []


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def create_window(options=None):
    win = FloatWindow(
        on_new_window=lambda: create_window(),
        on_save=lambda: save_windows(),
        on_quit=lambda: QApplication.instance().quit(),
    )
    if options:
        win.apply_options(options)
    windows.append(win)
    win.show()
    win.destroyed.connect(lambda: cleanup_window(win))
    return win


def cleanup_window(win):
    if win in windows:
        windows.remove(win)


def save_windows():
    ensure_data_dir()
    data = [w.to_dict() for w in windows]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_windows():
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for opts in data:
            create_window(opts)
    except Exception as e:
        print(f"Failed to load windows: {e}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ScreenFloat")
    app.setQuitOnLastWindowClosed(False)

    load_windows()
    if not windows:
        create_window()

    app.exec()


if __name__ == "__main__":
    main()
