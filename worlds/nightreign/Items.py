from typing import NamedTuple

from BaseClasses import Item, ItemClassification

from .game_data import NIGHTLORDS


class NightreignItem(Item):
    game: str = "Elden Ring Nightreign"


class ItemData(NamedTuple):
    code: int
    classification: ItemClassification = ItemClassification.filler


base_id = 3939000

# One flavorful filler item per Nightlord - no in-game effect in v1 (tracker
# only; see the project plan's scope decision to ship reads-only now and
# defer real item/character gating to a separate write-side research spike).
# create_items() creates enough copies of these to match the location count.
item_table = {
    f"{name} Trophy": ItemData(base_id + i)
    for i, name in enumerate(NIGHTLORDS)
}

item_name_to_id = {name: data.code for name, data in item_table.items()}
lookup_id_to_name = {data.code: name for name, data in item_table.items()}
