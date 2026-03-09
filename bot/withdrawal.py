"""Withdrawal helpers for dedicated storage stations.

These mirror the "deposit" concept, but are meant for stations where the Dedi is configured
(by in-game deposit/withdraw settings) to withdraw a fixed amount on each use.
"""

import time

import settings
import utils
import logs.gachalogs as logs
from bot import dedi_profiles


def withdraw_once():
    """Press use once with lag-compensated delay."""
    utils.press_key("Use")
    time.sleep(0.3 * settings.lag_offset)


def wood_dedi_withdraw_placeholder(station_name: str):
    """Profile-backed wood withdrawal station handler.

    Preference order:
    1. Station-specific JSON profile based on the teleporter/station name
    2. Generic wood placeholder JSON profile
    3. Fallback to a single Use press
    """
    profile_candidates = [
        f"withdraw_{dedi_profiles.slugify(station_name)}",
        "withdraw_wood_placeholder_default",
    ]
    profile_used = dedi_profiles.execute_first_available(
        profile_candidates,
        context=f"wood_dedi_withdraw_placeholder:{station_name}",
    )
    if profile_used:
        logs.logger.info(f"{station_name}: executed JSON withdrawal profile {profile_used}")
        return

    logs.logger.warning(
        f"{station_name}: wood withdrawal placeholder - only pressing Use once; update JSON profile once build is finalized"
    )
    withdraw_once()


def element_withdraw_at_charcoal_station():
    """Withdraw element from the element dedi at a charcoal station.

    Expected pre-condition: player is facing the charcoal station's yaw.
    Action: look left 90, pitch down 30, use (withdraw 3 element via dedi settings), then return.
    """
    if dedi_profiles.execute_profile("withdraw_charcoal_element", context="element_withdraw_at_charcoal_station"):
        return

    utils.turn_left(90)
    time.sleep(0.3 * settings.lag_offset)
    utils.turn_down(30)
    time.sleep(0.3 * settings.lag_offset)
    withdraw_once()
    utils.turn_up(30)
    time.sleep(0.3 * settings.lag_offset)
    utils.turn_right(90)
    time.sleep(0.3 * settings.lag_offset)



def run_named_withdraw_profile(profile_name: str | None, station_name: str | None = None):
    """Execute a named withdrawal profile with safe fallbacks.

    This lets station/task routing move to JSON without removing your current withdrawal helpers.
    """
    normalized = str(profile_name or '').strip().lower()

    if normalized:
        if dedi_profiles.execute_profile(normalized, context=f"run_named_withdraw_profile:{station_name or 'unknown'}"):
            return True
        if normalized in {'withdraw_charcoal_element', 'charcoal_element', 'element_charcoal'}:
            element_withdraw_at_charcoal_station()
            return True
        if normalized in {
            'withdraw_wood_placeholder_default',
            'wood_placeholder_default',
            'wood_placeholder',
        } and station_name:
            wood_dedi_withdraw_placeholder(station_name)
            return True

    if station_name:
        wood_dedi_withdraw_placeholder(station_name)
        return True
    return False
