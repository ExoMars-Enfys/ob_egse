from __future__ import annotations

# Std library
import logging
from tkinter import Tk, filedialog

logger = logging.getLogger("info_log")


def create_dialog_root() -> Tk:
    """Creates a hidden root window for the file dialog to ensure it appears on top of other windows."""
    root = Tk()
    root.withdraw()
    root.lift()
    root.attributes("-topmost", True)
    try:
        root.focus_force()
    except Exception:
        # Focus can fail depending on window manager state; dialog still works.
        pass
    root.update_idletasks()
    return root


def select_folder_dialog(title: str = "Select Folder") -> str | None:
    """Opens a folder selection dialog and returns the selected path."""
    root = None
    try:
        root = create_dialog_root()
        path = filedialog.askdirectory(title=title, parent=root)
        return path or None
    except Exception as exc:
        logger.error("Error opening folder selection dialog: %s", exc)
        return None
    finally:
        if root is not None:
            root.destroy()


def select_file_dialog(title: str = "Select File", filetypes: list[tuple[str, str]] | None = None) -> str | None:
    """Opens a file selection dialog and returns the selected file path."""
    root = None
    try:
        root = create_dialog_root()
        path = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes or [("All Files", "*.*")],
            parent=root,
        )
        return path or None
    except Exception as exc:
        logger.error("Error opening file selection dialog: %s", exc)
        return None
    finally:
        if root is not None:
            root.destroy()
