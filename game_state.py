# game_state.py
import tkinter as tk
from window_registry import close_all

game_running = False
root_ref = None
open_game_btn_ref = None


def init_game_state(root, open_game_btn):
    global root_ref, open_game_btn_ref
    root_ref = root
    open_game_btn_ref = open_game_btn


def lock_start_button():
    if open_game_btn_ref:
        open_game_btn_ref.config(
            state="disabled",
            fg="gray",
            text="ACCESS LOCKED"
        )


def unlock_start_button():
    if open_game_btn_ref:
        open_game_btn_ref.config(
            state="normal",
            fg="white",
            text="OPEN SECRET FILES"
        )


def start_game(show_password_window):
    global game_running
    if game_running:
        return

    game_running = True
    lock_start_button()
    show_password_window(root_ref)


def exit_game_confirmed():
    global game_running

    close_all()          # 🔥 закрывает ВСЁ, включая TrustSystem
    game_running = False
    unlock_start_button()