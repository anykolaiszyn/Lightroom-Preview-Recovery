from __future__ import annotations

from .gui import MainWindow


def main() -> int:
    window = MainWindow()
    window.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
