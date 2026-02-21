import time
from typing import Iterable, Optional, Sequence, Tuple

import logs.gachalogs as logs
import screen
import settings
import template
import variables
import windows


def _settle(seconds: Optional[float]) -> float:
    if seconds is None:
        seconds = float(getattr(settings, "auto_stack_settle_seconds", 0.75))
    return max(0.05, float(seconds))


def _safe_roi(region_key: str):
    region = template.roi_regions.get(region_key)
    if not region:
        raise KeyError(f"ROI region not found: {region_key}")
    return region


def anchor_from_region_and_global_keys(
    region_key: str,
    x_key: str,
    y_key: str,
    default: Tuple[float, float] = (0.5, 0.5),
) -> Tuple[float, float]:
    """Convert authored global coords into a normalized (x,y) anchor inside an ROI.

    This keeps old coordinate tuning usable while making the click reusable for any ROI.
    """
    try:
        region = _safe_roi(region_key)
        gx = variables.data.get(x_key)
        gy = variables.data.get(y_key)
        if gx is None or gy is None:
            return default

        rw = max(1, int(region["width"]))
        rh = max(1, int(region["height"]))
        rx = int(region["start_x"])
        ry = int(region["start_y"])

        rel_x = (float(gx) - float(rx)) / float(rw)
        rel_y = (float(gy) - float(ry)) / float(rh)

        # clamp to ROI to avoid invalid clicks if tuning drifts
        rel_x = min(max(rel_x, 0.0), 1.0)
        rel_y = min(max(rel_y, 0.0), 1.0)
        return (rel_x, rel_y)
    except Exception:
        return default


def click_roi_anchor(
    region_key: str,
    anchor: Tuple[float, float] = (0.5, 0.5),
    settle_seconds: Optional[float] = None,
    clicks: int = 1,
    label: Optional[str] = None,
) -> bool:
    """Click a normalized point inside an ROI.

    `anchor` is in normalized ROI coordinates (0..1, 0..1), authored against the ROI,
    not the full screen. This makes it reusable across resolutions/layout scaling.
    """
    try:
        region = _safe_roi(region_key)
        ax = min(max(float(anchor[0]), 0.0), 1.0)
        ay = min(max(float(anchor[1]), 0.0), 1.0)

        base_x = region["start_x"] + int(round(region["width"] * ax))
        base_y = region["start_y"] + int(round(region["height"] * ay))

        x = screen.map_x(base_x)
        y = screen.map_y(base_y)

        tag = label or region_key
        logs.logger.debug(
            f"ROI click '{tag}' via {region_key} anchor=({ax:.3f},{ay:.3f}) -> ({x},{y}) clicks={clicks}"
        )

        for _ in range(max(1, int(clicks))):
            windows.click(x, y)
            time.sleep(0.05 * settings.lag_offset)

        time.sleep(_settle(settle_seconds) * settings.lag_offset)
        return True
    except Exception as e:
        logs.logger.error(f"click_roi_anchor failed for {region_key}: {e}")
        return False


def click_template_in_roi(
    template_keys: Sequence[str],
    thresholds: Optional[Sequence[float]] = None,
    settle_seconds: Optional[float] = None,
    label: Optional[str] = None,
) -> bool:
    """Try clicking by template match center for one or more template keys."""
    if not template_keys:
        return False

    if thresholds is None:
        thresholds = [0.7] * len(template_keys)

    try:
        for idx, key in enumerate(template_keys):
            th = float(thresholds[idx]) if idx < len(thresholds) else float(thresholds[-1])
            try:
                if not template.check_template(key, th):
                    continue
                loc = template.return_location(key, th)
                if not loc or loc == 0:
                    continue

                region = _safe_roi(key)
                origin_x = screen.map_x(region["start_x"])
                origin_y = screen.map_y(region["start_y"])

                img = template._read_icon(key)
                w = int(img.shape[1]) if img is not None else 20
                h = int(img.shape[0]) if img is not None else 20

                click_x = int(origin_x + loc[0] + (w / 2))
                click_y = int(origin_y + loc[1] + (h / 2))

                windows.click(click_x, click_y)
                logs.logger.debug(
                    f"template ROI click '{label or key}' via {key} @ ({click_x},{click_y})"
                )
                time.sleep(_settle(settle_seconds) * settings.lag_offset)
                return True
            except Exception as e:
                logs.logger.debug(f"template ROI click failed for {key}: {e}")
                continue
    except Exception as e:
        logs.logger.debug(f"click_template_in_roi failed: {e}")

    return False


def click_button(
    *,
    label: str,
    fallback_region_key: str,
    fallback_anchor: Tuple[float, float],
    template_keys: Optional[Sequence[str]] = None,
    template_thresholds: Optional[Sequence[float]] = None,
    prefer_template: bool = False,
    settle_seconds: Optional[float] = None,
    clicks: int = 1,
) -> bool:
    """Reusable UI-button click helper.

    Strategy:
      - If prefer_template=True, attempt template-based center click first.
      - Always fallback to ROI-anchor click (no icon detection required).
    """
    if prefer_template and template_keys:
        if click_template_in_roi(
            template_keys=template_keys,
            thresholds=template_thresholds,
            settle_seconds=settle_seconds,
            label=label,
        ):
            return True

    return click_roi_anchor(
        region_key=fallback_region_key,
        anchor=fallback_anchor,
        settle_seconds=settle_seconds,
        clicks=clicks,
        label=label,
    )


def click_auto_stack(
    settle_seconds: Optional[float] = None,
    prefer_template: bool = False,
    clicks: int = 1,
) -> bool:
    """Click the structure-side Auto Stack button.

    Defaults to ROI-anchor clicking to avoid template recognition failures, but can still
    use template matching when desired.
    """
    anchor = anchor_from_region_and_global_keys(
        region_key="auto_stack",
        x_key="auto_stack_x",
        y_key="auto_stack_y",
        default=(0.38, 0.23),  # close to existing tuned coords inside ROI
    )

    return click_button(
        label="auto_stack",
        fallback_region_key="auto_stack",
        fallback_anchor=anchor,
        template_keys=["auto_stack_icon", "auto_stack"],
        template_thresholds=[0.65, 0.70],
        prefer_template=prefer_template,
        settle_seconds=settle_seconds,
        clicks=clicks,
    )
