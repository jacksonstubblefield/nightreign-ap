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

# One progression "Access" item per Nightlord tracking whether this player has actually earned
# it (see game_data.py's ACCESS_NIGHTLORDS - this includes Tricephalos even though it needs no
# in-game flag write, since AP ownership and in-game visibility aren't the same thing), plus the
# flavorful filler items below. BASE_ID+0..7 used to be flavor-only "Trophy" items with no
# in-game effect; those have been removed in favor of Randomized Weapon/Talisman (real dropped
# items), so those codes are retired rather than reused, and Access items still start at
# BASE_ID+8.. to avoid collisions with any old seed still holding a Trophy item id.
item_table = {
    f"{name} Access": ItemData(BASE_ID + len(NIGHTLORDS) + i, ItemClassification.progression)
    for i, name in enumerate(ACCESS_NIGHTLORDS)
} | {
    # Client-side, receiving this resolves to a real dropped weapon (see client.py's
    # _roll_weapon_drop/_deliver_pending_weapons) only when the randomize_weapons option is on
    # for this slot - with it off, this item is never placed in the pool at all (see
    # __init__.py's get_filler_item_name).
    "Randomized Weapon": ItemData(BASE_ID + len(NIGHTLORDS) + len(ACCESS_NIGHTLORDS)),
    # Same shape as "Randomized Weapon" above, gated by the randomize_talismans option instead.
    "Randomized Talisman": ItemData(BASE_ID + len(NIGHTLORDS) + len(ACCESS_NIGHTLORDS) + 1),
}

# get_filler_item_name() must only ever choose from FILLER_ITEM_NAMES - not item_table's full key
# set, since once item_table holds progression Access items, choosing from all of it would let
# AP's own pool-repair logic (start_inventory_from_pool depletion, plando swaps) hand out an
# Access item as "random filler", silently breaking gating for whoever receives it. No item is
# unconditionally filler anymore (both Randomized Weapon/Talisman are gated by their own option -
# see __init__.py's get_filler_item_name), so this starts empty.
FILLER_ITEM_NAMES: list[str] = []

item_name_to_id = {name: data.code for name, data in item_table.items()}
lookup_id_to_name = {data.code: name for name, data in item_table.items()}
