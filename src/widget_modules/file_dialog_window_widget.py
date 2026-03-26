# Std library
import logging

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
