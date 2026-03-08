"""Withdrawal helpers for dedicated storage stations.

These mirror the "deposit" concept, but are meant for stations where the Dedi is configured
(by in-game deposit/withdraw settings) to withdraw a fixed amount on each use.

For now, wood_dedi_station_1/2 are intentionally placeholders.
"""

import time

import settings
import logs
import utils


def withdraw_once():
    """Press use once with lag-compensated delay."""
    utils.press_key("Use")
    time.sleep(0.3 * settings.lag_offset)


def wood_dedi_withdraw_placeholder(station_name: str):
    """Placeholder for wood withdrawal stations.

    The user will finalize the build/angles; for now this simply hits Use once.
    """
    logs.logger.warning(
        f"{station_name}: wood withdrawal placeholder - only pressing Use once; update logic once build is finalized"
    )
    withdraw_once()


def element_withdraw_at_charcoal_station():
    """Withdraw element from the element dedi at a charcoal station.

    Expected pre-condition: player is facing the charcoal station's yaw.
    Action: look left 90, pitch down 30, use (withdraw 3 element via dedi settings), then return.
    """
    utils.turn_left(90)
    time.sleep(0.3 * settings.lag_offset)
    utils.turn_down(30)
    time.sleep(0.3 * settings.lag_offset)
    withdraw_once()
    utils.turn_up(30)
    time.sleep(0.3 * settings.lag_offset)
    utils.turn_right(90)
    time.sleep(0.3 * settings.lag_offset)
