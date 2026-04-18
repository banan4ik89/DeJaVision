# Project Structure

`main.py` remains the root entry point and delegates startup into `abebe/app.py`.

## Runtime layout

- `abebe/core/`: runtime state and shared services.
- `abebe/events/`: runtime scripted events used by the UI flow.
- `abebe/ui/`: Tkinter windows, dialogs, and launcher flows.
- `abebe/maze/`: maze gameplay, pause menu, raycast/OpenGL renderers.
- `abebe/entities/`: reusable enemy and item logic shared by maze modules.
- `data/app/`: desktop UI assets, Abebe cutscenes, story files, and app-specific media.
- `data/audio/`: music and sound effects.
- `data/levels/`: custom maps plus level-related shared assets.
- `userdata/`: mutable local player settings.

## Data layout

- `data/app/pane_os/`: desktop shell visuals used by `main.py` and window UIs.
- `data/app/abebe/`: Abebe gifs, voice lines, and watcher/eye animations.
- `data/app/story/`: story files like `12340.txt`, `1401.zip`, `death.png`, `info.txt`, and easter egg assets.
- `data/audio/music/`: background and overlay music tracks.
- `data/audio/sfx/`: standalone sound effects.
- `data/levels/custom_maps/`: editable user maps from the level editor.
- `data/levels/assets/`: maze textures, doors, hands, enemies, orbs, and level SFX.

## Main call flow

1. `main.py`
2. `abebe/app.py`
3. `abebe/ui/password_window.py`
4. Maze launchers in `abebe/maze/` plus shared gameplay modules in `abebe/core/` and `abebe/entities/`

## Non-runtime folders

- `legacy/`: backups, prototypes, and superseded engine variants.
- `packaging/specs/`: PyInstaller `.spec` files.
- `tools/`: one-off helper scripts like `ORB.py`.
