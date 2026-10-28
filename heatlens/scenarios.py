from __future__ import annotations

import math
from typing import Any


def simulate_interventions(
    site_area_m2: float,
    tree_count: int,
    tree_canopy_diameter_m: float,
    shade_structure_area_m2: float,
    pavement_conversion_area_m2: float,
    permeable_conversion_percent: float,
) -> dict[str, Any]:
    """Estimate intervention footprints; this does not predict cooling."""
    values = {
        "site_area_m2": site_area_m2,
        "tree_canopy_diameter_m": tree_canopy_diameter_m,
        "shade_structure_area_m2": shade_structure_area_m2,
        "pavement_conversion_area_m2": pavement_conversion_area_m2,
        "permeable_conversion_percent": permeable_conversion_percent,
    }
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values.values()
    ):
        raise ValueError("Scenario values must be finite numbers")
    if site_area_m2 <= 0:
        raise ValueError("site_area_m2 must be greater than zero")
    nonnegative_values = (
        tree_canopy_diameter_m,
        shade_structure_area_m2,
        pavement_conversion_area_m2,
        permeable_conversion_percent,
    )
    if any(value < 0 for value in nonnegative_values):
        raise ValueError("Intervention areas, canopy diameter, and percentage cannot be negative")
    if permeable_conversion_percent > 100:
        raise ValueError("permeable_conversion_percent cannot exceed 100")
    if isinstance(tree_count, bool) or not isinstance(tree_count, int) or tree_count < 0:
        raise ValueError("tree_count must be a non-negative integer")

    projected_canopy_area = tree_count * math.pi * (tree_canopy_diameter_m / 2) ** 2
    tree_area = min(site_area_m2, projected_canopy_area)
    structure_area = min(site_area_m2, shade_structure_area_m2)
    converted_area = min(site_area_m2, pavement_conversion_area_m2)
    permeable_area = converted_area * permeable_conversion_percent / 100

    def area_share(area: float) -> float:
        return round(area / site_area_m2 * 100, 1)

    return {
        "site_area_m2": site_area_m2,
        "scenarios": {
            "trees": {
                "label": "Tree canopy",
                "area_m2": round(tree_area, 1),
                "site_area_percent": area_share(tree_area),
                "metric_label": "Projected canopy",
                "assumption": (
                    "Circular canopy projections use the entered mature canopy "
                    "diameter, assume no overlap, and are capped at site area."
                ),
            },
            "shade_structure": {
                "label": "Shade structure",
                "area_m2": round(structure_area, 1),
                "site_area_percent": area_share(structure_area),
                "metric_label": "Proposed covered area",
                "assumption": (
                    "Entered structure footprint is used as a proxy for covered "
                    "area; orientation, shadows, and existing shade are not modeled."
                ),
            },
            "permeable_surface": {
                "label": "Pavement conversion",
                "area_m2": round(converted_area, 1),
                "site_area_percent": area_share(converted_area),
                "permeable_area_m2": round(permeable_area, 1),
                "impervious_reduction_percent_of_site": area_share(permeable_area),
                "metric_label": "Area converted",
                "assumption": (
                    "Converted area is assumed to be existing impervious pavement; "
                    "only the entered permeable share is counted as a modeled "
                    "impervious-area reduction."
                ),
            },
        },
    }
