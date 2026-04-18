# game_state.py
import tkinter as tk
from abebe.ui.window_registry import close_all

game_running = False
root_ref = None
open_game_btn_ref = None


def _set_open_button_state(enabled, text, color):
    if not open_game_btn_ref:
        return

    if isinstance(open_game_btn_ref, dict):
        open_game_btn_ref["enabled"] = enabled
        canvas = open_game_btn_ref.get("canvas")
        text_item = open_game_btn_ref.get("text_item")
        shadow_item = open_game_btn_ref.get("text_shadow_item")
        if canvas is not None and text_item is not None:
            canvas.itemconfigure(text_item, fill=color, text=text)
        if canvas is not None and shadow_item is not None:
            canvas.itemconfigure(shadow_item, text=text)
        return

    open_game_btn_ref.config(
        state="normal" if enabled else "disabled",
        fg=color,
        text=text
    )


def init_game_state(root, open_game_btn):
    global root_ref, open_game_btn_ref
    root_ref = root
    open_game_btn_ref = open_game_btn


def lock_start_button():
    _set_open_button_state(False, "secret_files.locked", "#b5b5b5")


def unlock_start_button():
    _set_open_button_state(True, "secret_files/", "#f5f5f5")


def start_game(show_password_window):
    global game_running
    if game_running:
        return

    game_running = True
    lock_start_button()
    show_password_window(root_ref)


def exit_game_confirmed():
    global game_running

    close_all()          # рџ”Ґ Р·Р°РєСЂС‹РІР°РµС‚ Р’РЎРЃ, РІРєР»СЋС‡Р°СЏ TrustSystem
    game_running = False
    unlock_start_button()

