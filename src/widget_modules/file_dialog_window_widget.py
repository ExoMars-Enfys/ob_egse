# Std library
import logging
from tkinter import filedialog

# Added packages
from tkinter import Tk

# Local modules
# core
from core_modules import constants as const

info_log = logging.getLogger("info_log")


#! To be moved to Widgets
def create_dialog_root() -> Tk:
    root = Tk()
    root.withdraw()
    root.lift()
    root.attributes("-topmost", True)
    root.focus_force()
    root.update_idletasks()
    return root


def select_folder_dialog(title: str = "Select Folder") -> str | None:
    root = create_dialog_root()
    try:
        path = filedialog.askdirectory(title=title)
        return path or None
    finally:
        root.destroy()


def select_file_dialog(title: str = "Select File", filetypes: list[tuple[str, str]] | None = None) -> str | None:
    root = create_dialog_root()
    try:
        path = filedialog.askopenfilename(title=title, filetypes=filetypes or [("All Files", "*.*")])
        return path or None
    finally:
        root.destroy()
