"""Steam Forge interaction logic.

Steam Forge differs from the standard forge because it requires Element to activate.
This module focuses on:
- Taking charcoal (filtering the structure inventory to avoid ingots)
- Transferring wood+element into the forge
- Turning the forge on (only when the on-prompt is detected)
"""

import time

import settings
import utils
import logs

from ASA.structures import inventory
import template


def _sleep_ui(mult: float = 1.0):
    time.sleep(mult * settings.lag_offset)


def open_inventory():
    utils.press_key("Use")
    _sleep_ui(0.6)


def close_inventory():
    utils.press_key("Inventory")  # closes inventory
    _sleep_ui(0.5)


def take_all_charcoal_only():
    """Open forge inventory, filter to charcoal, transfer all from forge -> player."""
    open_inventory()
    _sleep_ui(0.8)

    # Filter the STRUCTURE side search bar.
    inventory.search_in_object("charcoal")
    _sleep_ui(0.6)

    # Transfer all FROM structure.
    inventory.transfer_all_from()
    _sleep_ui(0.8)

    close_inventory()


def transfer_all_to_forge():
    """Open forge inventory and transfer all from player inventory -> forge."""
    open_inventory()
    _sleep_ui(0.8)

    # Transfer all FROM inventory (player) to structure.
    inventory.transfer_all_inventory()
    _sleep_ui(0.8)

    close_inventory()


def try_turn_on():
    """Turn on the forge only if the 'Turn On' prompt is visible.

    This is important because a stray extra use can toggle it OFF.
    """
    # Check for the on prompt in the interaction HUD region.
    if template.check_template("forge_ready_for_activation", bounds="forge_prompt", threshold=0.75, debug=False):
        utils.press_key("Use")
        _sleep_ui(0.8)
        return True

    # If it's already on (turn-off prompt), do nothing.
    if template.check_template("forge_already_on", bounds="forge_prompt", threshold=0.75, debug=False):
        return False

    # Not ready / no fuel or prompt not visible.
    return False
