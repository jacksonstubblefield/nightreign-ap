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

# One flavorful filler item per Nightlord, plus one progression "Access" item per Nightlord
# tracking whether this player has actually earned it (see game_data.py's ACCESS_NIGHTLORDS -
# this includes Tricephalos even though it needs no in-game flag write, since AP ownership and
# in-game visibility aren't the same thing). Trophy codes stay at BASE_ID+0..7 so existing seeds'
# item ids don't shift; Access items append at BASE_ID+8.. with no collisions.
item_table = {
    f"{name} Trophy": ItemData(BASE_ID + i)
    for i, name in enumerate(NIGHTLORDS)
} | {
    f"{name} Access": ItemData(BASE_ID + len(NIGHTLORDS) + i, ItemClassification.progression)
    for i, name in enumerate(ACCESS_NIGHTLORDS)
} | {
    # Appended after the Access items rather than interleaved, so existing seeds' Trophy/Access
    # ids never shift. Client-side, receiving this resolves to a real dropped weapon (see
    # client.py's _roll_weapon_drop/_deliver_pending_weapons) only when the randomize_weapons
    # option is on for this slot - with it off, this item is never placed in the pool at all
    # (see __init__.py's get_filler_item_name), so it behaves like any other flavorful filler.
    "Randomized Weapon": ItemData(BASE_ID + len(NIGHTLORDS) + len(ACCESS_NIGHTLORDS)),
    # Same shape as "Randomized Weapon" above, gated by the randomize_talismans option instead -
    # appended after it so existing seeds' ids still never shift.
    "Randomized Talisman": ItemData(BASE_ID + len(NIGHTLORDS) + len(ACCESS_NIGHTLORDS) + 1),
}

# get_filler_item_name() must only ever choose from FILLER_ITEM_NAMES (extended with
# "Randomized Weapon" there when randomize_weapons is on) - not item_table's full key set, since
# once item_table holds progression Access items, choosing from all of it would let AP's own
# pool-repair logic (start_inventory_from_pool depletion, plando swaps) hand out an Access item
# as "random filler", silently breaking gating for whoever receives it.
FILLER_ITEM_NAMES = [f"{name} Trophy" for name in NIGHTLORDS]

item_name_to_id = {name: data.code for name, data in item_table.items()}
lookup_id_to_name = {data.code: name for name, data in item_table.items()}
