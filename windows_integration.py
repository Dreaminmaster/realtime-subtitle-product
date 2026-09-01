"""Narrow Win32 helpers that Qt does not expose directly."""

from __future__ import annotations

import os


def apply_no_activate_tool_window(widget) -> bool:
    """Keep an overlay above apps without entering Alt-Tab or taking focus.

    Qt's WindowDoesNotAcceptFocus is necessary but not sufficient on every
    Windows/Qt combination. WS_EX_NOACTIVATE and WS_EX_TOOLWINDOW make the
    native HWND match the expected caption-overlay behavior.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = int(widget.winId())
        gwl_exstyle = -20
        ws_ex_toolwindow = 0x00000080
        ws_ex_noactivate = 0x08000000
        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_nozorder = 0x0004
        swp_noactivate = 0x0010
        swp_framechanged = 0x0020

        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        style = int(get_style(hwnd, gwl_exstyle))
        set_style(hwnd, gwl_exstyle, style | ws_ex_toolwindow | ws_ex_noactivate)
        user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            swp_nosize
            | swp_nomove
            | swp_nozorder
            | swp_noactivate
            | swp_framechanged,
        )
        return True
    except Exception:
        return False
