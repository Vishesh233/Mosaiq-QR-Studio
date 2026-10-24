import customtkinter as ctk

from utils import window_guard
from utils.theme_manager import ThemeManager
from ui.brand_logo import apply_window_icon


def ask_save_changes(parent):
    """"Save changes?" with [Save] [Don't save] [Cancel]. Returns "save", "discard" or "cancel"."""
    theme = ThemeManager.get_theme()
    box = ctk.CTkToplevel(parent)
    box.title("Settings")
    apply_window_icon(box)
    box.configure(fg_color=theme["background"])
    box.resizable(False, False)
    box.transient(parent)
    answer = {"value": "cancel"}

    def choose(value):
        answer["value"] = value
        box.destroy()

    ctk.CTkLabel(box, text="Save changes?", font=("Segoe UI Semibold", 17),
                 text_color=theme["text"]).pack(anchor="w", padx=26, pady=(24, 4))
    ctk.CTkLabel(box, text="You changed some settings. Save them before leaving?",
                 font=("Segoe UI", 13), text_color=theme["text_secondary"],
                 wraplength=380, justify="left").pack(anchor="w", padx=26)
    row = ctk.CTkFrame(box, fg_color="transparent")
    row.pack(fill="x", padx=26, pady=(22, 22))
    ctk.CTkButton(row, text="Save", width=110, height=38, corner_radius=10,
                  fg_color=theme["primary"], hover_color=theme["primary_hover"],
                  text_color=theme["on_primary"], font=("Segoe UI Semibold", 13),
                  command=lambda: choose("save")).pack(side="right")
    ctk.CTkButton(row, text="Don't save", width=110, height=38, corner_radius=10,
                  fg_color="transparent", border_width=1, border_color=theme["border"],
                  hover_color=theme["card_hover"], text_color=theme["text"],
                  command=lambda: choose("discard")).pack(side="right", padx=(0, 10))
    ctk.CTkButton(row, text="Cancel", width=90, height=38, corner_radius=10,
                  fg_color="transparent", border_width=1, border_color=theme["border"],
                  hover_color=theme["card_hover"], text_color=theme["text"],
                  command=lambda: choose("cancel")).pack(side="right", padx=(0, 10))
    box.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
    box.bind("<Escape>", lambda _e: choose("cancel"))
    box.update_idletasks()
    width, height = max(box.winfo_reqwidth(), 440), box.winfo_reqheight()
    top = parent.winfo_toplevel()
    scaling = box._get_window_scaling()
    at = window_guard.centred_over(
        (top.winfo_rootx(), top.winfo_rooty(), top.winfo_rootx() + top.winfo_width(),
         top.winfo_rooty() + top.winfo_height()),
        window_guard.work_areas(), (round(width * scaling), round(height * scaling)))
    box.geometry(f"{width}x{height}" + (f"+{at[0]}+{at[1]}" if at else ""))     # on screen, over the app
    box.after(50, box.grab_set)
    parent.wait_window(box)
    return answer["value"]
