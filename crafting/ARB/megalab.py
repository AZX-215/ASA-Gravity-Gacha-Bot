import time

import ASA.strucutres.inventory
import logs.gachalogs as logs
import settings
import template
import utils
import variables
import windows
import screen


def is_open_megalab() -> bool:
    """Returns True if an inventory is open AND the title matches Makeshift Megalab."""
    if not ASA.strucutres.inventory.is_open():
        return False
    return template.check_template("megalab", 0.7)


def _click_first_slot():
    """Clicks the first (top-left) slot in the structure-side grid."""
    x = ASA.strucutres.inventory.inv_slots["x"] + 30
    y = ASA.strucutres.inventory.inv_slots["y"] + 30

    if screen.screen_resolution == 1080:
        x = x * 0.75
        y = y * 0.75

    windows.move_mouse(x, y)
    windows.click(x, y)
    time.sleep(0.10 * settings.lag_offset)


def select_inventory_tab():
    """Select the structure-side INVENTORY tab (right panel)."""
    ASA.strucutres.inventory.select_object_inventory_tab()


def select_crafting_tab():
    """Select the structure-side CRAFTING tab (right panel)."""
    ASA.strucutres.inventory.select_object_crafting_tab()


def transfer_filtered_to_player(search_term: str = "spark") -> bool:
    """
    From the Megalab INVENTORY tab:
    - Types search_term in the structure search bar
    - Clicks 'Transfer All From' (expected to respect the search filter)

    This is intentionally simple: if there are no matching items, transfer does nothing.
    """
    if not ASA.strucutres.inventory.is_open():
        logs.logger.error("Megalab transfer requested but no structure inventory is open.")
        return False

    select_inventory_tab()
    ASA.strucutres.inventory.search_in_object(search_term)
    time.sleep(0.15 * settings.lag_offset)
    ASA.strucutres.inventory.transfer_all_from()
    time.sleep(0.15 * settings.lag_offset)
    return True


def craft_from_crafting_tab(search_term: str = "spark", craft_seconds: float = 2.0) -> bool:
    """
    From the Megalab CRAFTING tab:
    - Types search_term in the structure search bar
    - Clicks the first slot (assumes filtered result is top-left)
    - Spams 'A' for craft_seconds to craft as much as possible.
    """
    if not ASA.strucutres.inventory.is_open():
        logs.logger.error("Megalab craft requested but no structure inventory is open.")
        return False

    select_crafting_tab()
    ASA.strucutres.inventory.search_in_object(search_term)
    time.sleep(0.15 * settings.lag_offset)

    _click_first_slot()

    start = time.time()
    while (time.time() - start) < craft_seconds:
        utils.press_key("a")
        time.sleep(0.03 * settings.lag_offset)

    time.sleep(0.15 * settings.lag_offset)
    return True


def run_sparkpowder_cycle(craft_seconds: float = 2.0) -> bool:
    """
    Convenience helper for your SparkPowder task:
    1) Transfer existing sparkpowder out of the Megalab (filtered)
    2) Craft more sparkpowder

    Deposit into Dedis is handled by the station task, not here.
    """
    if not is_open_megalab():
        logs.logger.error("Expected Megalab inventory, but Megalab template was not detected.")
        return False

    transfer_filtered_to_player("spark")
    craft_from_crafting_tab("spark", craft_seconds=craft_seconds)
    return True


def run_gunpowder_cycle(craft_seconds: float = 2.0) -> bool:
    """Same flow as run_sparkpowder_cycle, but filtered to Gunpowder."""
    if not is_open_megalab():
        logs.logger.error("Expected Megalab inventory, but Megalab template was not detected.")
        return False

    # Typing the full item name keeps the first-slot assumption reliable.
    transfer_filtered_to_player("gunpowder")
    craft_from_crafting_tab("gunpowder", craft_seconds=craft_seconds)
    return True
