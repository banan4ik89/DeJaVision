"""
Reusable facade for optional maze-level entities.

Import this module inside any maze file when you want to enable shared
entity systems such as bombs, mannequin, or hexagaze/cubesentry.
The maze can then decide which symbols to place on MAP and which systems
to initialize.
"""

from bomb import (
    capture_snapshot as capture_bomb_snapshot,
    collect_bomb_pickups,
    detonate_bomb_at_cell,
    get_hand_pil as get_bomb_hand_pil,
    get_targeted_floor_cell,
    load_bomb_assets,
    pickup_bombs,
    place_bomb,
    spawn_bomb_explosion,
    trigger_activator,
    update_bomb_system,
)
from hexagaze import (
    build_visible_cells as build_hexagaze_visible_cells,
    collect_sentries,
    generate_blind_offsets,
    get_frame_index as get_hexagaze_frame_index,
    get_roll_frame_index as get_hexagaze_roll_frame_index,
    is_blocked_by_sentry,
    load_hexagaze_assets,
    update_sentries,
)
from mannequin import (
    can_see_player as mannequin_can_see_player,
    create_mannequin_state,
    damage as damage_mannequin,
    get_frame_index as get_mannequin_frame_index,
    load_mannequin_assets,
    player_can_see as player_can_see_mannequin,
    push_back as push_mannequin_back,
    update_state as update_mannequin_state,
)


BOMB_SYMBOL = "B"
MANNEQUIN_SYMBOL = "M"
HEXAGAZE_SYMBOL = "C"

