from __future__ import annotations

from .gui import MainWindow, SplashScreen


def main() -> int:
    splash = SplashScreen()
    splash.on_dismiss(lambda: MainWindow().mainloop())
    splash.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
