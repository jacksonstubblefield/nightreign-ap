from typing import NamedTuple

from BaseClasses import Item, ItemClassification

from .game_data import ACCESS_NIGHTLORDS, NIGHTLORDS


class NightreignItem(Item):
    game: str = "Elden Ring Nightreign"


class ItemData(NamedTuple):
    code: int
    classification: ItemClassification = ItemClassification.filler


base_id = 3939000

# One flavorful filler item per Nightlord, plus one progression "Access" item per Nightlord
# tracking whether this player has actually earned it (see game_data.py's ACCESS_NIGHTLORDS -
# this includes Tricephalos even though it needs no in-game flag write, since AP ownership and
# in-game visibility aren't the same thing). Trophy codes stay at base_id+0..7 so existing seeds'
# item ids don't shift; Access items append at base_id+8.. with no collisions.
item_table = {
    f"{name} Trophy": ItemData(base_id + i)
    for i, name in enumerate(NIGHTLORDS)
} | {
    f"{name} Access": ItemData(base_id + len(NIGHTLORDS) + i, ItemClassification.progression)
    for i, name in enumerate(ACCESS_NIGHTLORDS)
}

# get_filler_item_name() must only ever choose from this, not item_table's
# full key set - once item_table holds progression Access items, choosing
# from all of it would let AP's own pool-repair logic (start_inventory_from_pool
# depletion, plando swaps) hand out an Access item as "random filler",
# silently breaking gating for whoever receives it.
FILLER_ITEM_NAMES = [f"{name} Trophy" for name in NIGHTLORDS]

item_name_to_id = {name: data.code for name, data in item_table.items()}
lookup_id_to_name = {data.code: name for name, data in item_table.items()}
