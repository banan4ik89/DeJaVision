current_theme = "normal"

THEMES = {
    "normal": {
        "bg": "black",
        "fg": "white",
        "accent": "lime",
        "danger": "red"
    },
    "restricted": {
        "bg": "#0a0a0a",
        "fg": "#cccccc",
        "accent": "orange",
        "danger": "red"
    },
    "corrupted": {
        "bg": "black",
        "fg": "red",
        "accent": "red",
        "danger": "darkred"
    }
}


def set_theme(name):
    global current_theme
    if name in THEMES:
        current_theme = name


def get_color(key):
    return THEMES[current_theme][key]