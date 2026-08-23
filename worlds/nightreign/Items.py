from typing import NamedTuple

from BaseClasses import Item, ItemClassification

from .game_data import ACCESS_NIGHTLORDS, NIGHTLORDS


class NightreignItem(Item):
    """Base Nightreign item class, used to set the game name for all items in this world.

    Args:
        Item (_type_): _description_
    """
    game: str = "Elden Ring Nightreign"


class ItemData(NamedTuple):
    """Item data for Nightreign items, used to store the item code and classification.

    Args:
        NamedTuple (_type_): _description_
    """
    code: int
    classification: ItemClassification = ItemClassification.filler


BASE_ID = 3939000

# One progression "Access" item per Nightlord tracking whether it's been earned (see
# ACCESS_NIGHTLORDS). BASE_ID+0..7 were retired flavor-only "Trophy" items; Access items start
# at BASE_ID+8.. to avoid colliding with any old seed still holding a Trophy item id.
item_table = {
    f"{name} Access": ItemData(BASE_ID + len(NIGHTLORDS) + i, ItemClassification.progression)
    for i, name in enumerate(ACCESS_NIGHTLORDS)
} | {
    # Client-side, receiving this resolves to a real dropped weapon (see client.py's
    # _roll_weapon_drop) only when randomize_weapons is on for this slot - with it off, this
    # item is never placed in the pool at all (see __init__.py's get_filler_item_name).
    "Randomized Weapon": ItemData(BASE_ID + len(NIGHTLORDS) + len(ACCESS_NIGHTLORDS)),
    # Same shape as "Randomized Weapon" above, gated by the randomize_talismans option instead.
    "Randomized Talisman": ItemData(BASE_ID + len(NIGHTLORDS) + len(ACCESS_NIGHTLORDS) + 1),
}

# get_filler_item_name() must only ever choose from FILLER_ITEM_NAMES, not item_table's full key
# set - otherwise AP's pool-repair logic could hand out a progression Access item as "random
# filler". No item is unconditionally filler anymore, so this starts empty.
FILLER_ITEM_NAMES: list[str] = []

item_name_to_id = {name: data.code for name, data in item_table.items()}
lookup_id_to_name = {data.code: name for name, data in item_table.items()}
