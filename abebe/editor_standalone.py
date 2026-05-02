import tkinter as tk

from abebe.ui.level_editor_window import show_level_editor


def run():
    root = tk.Tk()
    root.withdraw()
    show_level_editor(root, force_new=True)
    root.mainloop()


if __name__ == "__main__":
    run()
