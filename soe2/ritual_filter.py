"""Filter in the Ritual window: the game has a setting with no switch in its menus - apply_item_filter_to_ritual in
poe2_production_Config.ini - that makes your item filter apply to the Ritual altar's Favours window. Found by Ryonnen
(reddit), shown by NeverSink.

3.0.7 (GGG policy audit: changing the game's files is not allowed): the app never opens, reads or writes that file.
It only shows the words to follow, copies the line to look for and opens the folder in Explorer. The old status
(read from the file) and the Turn it on button (wrote it, after waiting for the game to close) are gone."""
import os
import sys

KEY = "apply_item_filter_to_ritual"
FILE = "poe2_production_Config.ini"
CREDIT = "Found by Ryonnen (reddit), shown by NeverSink"
LINE_OFF = KEY + "=false"
LINE_ON = KEY + "=true"
HOW = (f"To use your item filter in the Ritual window: close the game, open Documents\\My Games\\Path of Exile 2\\"
       f"{FILE}, find {LINE_OFF} and change it to {LINE_ON}, then save.")


def documents():
    """Your Documents folder (where Windows really keeps it - OneDrive may have moved it)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
            docs = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(docs), 0, None, ctypes.byref(p)) == 0:
                out = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                if out:
                    return out
        except Exception:                                  # (the usual place below)
            from . import buglog
            buglog.caught()
    return os.path.join(os.path.expanduser("~"), "Documents")


def folder(docs=None):
    """-> the game's settings folder in Documents (to open in Explorer - only the folder is opened, never the file)."""
    base = os.path.join(docs or documents(), "My Games", "Path of Exile 2")
    return base if os.path.isdir(base) else (docs or documents())
