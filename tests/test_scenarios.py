import math

import pytest

from heatlens.scenarios import simulate_interventions


def run_scenario(**overrides):
    inputs = {
        "site_area_m2": 1_000,
        "tree_count": 4,
        "tree_canopy_diameter_m": 6,
        "shade_structure_area_m2": 200,
        "pavement_conversion_area_m2": 300,
        "permeable_conversion_percent": 50,
    }
    inputs.update(overrides)
    return simulate_interventions(**inputs)


def test_scenario_area_estimates_and_permeable_fraction():
    result = run_scenario()
    scenarios = result["scenarios"]

    assert scenarios["trees"]["area_m2"] == round(4 * math.pi * 3**2, 1)
    assert scenarios["shade_structure"]["area_m2"] == 200
    assert scenarios["permeable_surface"]["area_m2"] == 300
    assert scenarios["permeable_surface"]["permeable_area_m2"] == 150
    assert scenarios["permeable_surface"]["impervious_reduction_percent_of_site"] == 15
    assert scenarios["trees"]["site_area_percent"] == 11.3


def test_scenario_areas_are_capped_by_the_assumed_site_area():
    result = run_scenario(
        site_area_m2=100,
        tree_count=100,
        shade_structure_area_m2=200,
        pavement_conversion_area_m2=300,
    )
    scenarios = result["scenarios"]

    assert scenarios["trees"]["area_m2"] == 100
    assert scenarios["shade_structure"]["area_m2"] == 100
    assert scenarios["permeable_surface"]["area_m2"] == 100


@pytest.mark.parametrize(
    "overrides",
    [
        {"site_area_m2": 0},
        {"tree_count": -1},
        {"tree_count": 1.5},
        {"tree_canopy_diameter_m": -1},
        {"shade_structure_area_m2": float("inf")},
        {"permeable_conversion_percent": 101},
        {"permeable_conversion_percent": -1},
    ],
)
def test_invalid_scenario_assumptions_are_rejected(overrides):
    with pytest.raises(ValueError):
        run_scenario(**overrides)
