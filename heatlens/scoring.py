from __future__ import annotations

import math
from typing import Any

DEFAULT_TEMPERATURE_WEIGHT = 0.65


def _percentile_ranks(values: list[float | None]) -> list[float | None]:
    valid_values = sorted(value for value in values if value is not None)
    if not valid_values:
        return [None] * len(values)

    ranks: dict[float, float] = {}
    start = 0
    while start < len(valid_values):
        end = start + 1
        while end < len(valid_values) and valid_values[end] == valid_values[start]:
            end += 1
        ranks[valid_values[start]] = (
            0.5
            if len(valid_values) == 1
            else ((start + end - 1) / 2) / (len(valid_values) - 1)
        )
        start = end

    return [ranks.get(value) if value is not None else None for value in values]


def prioritize_samples(
    samples: list[dict[str, Any]],
    temperature_weight: float = DEFAULT_TEMPERATURE_WEIGHT,
) -> list[dict[str, Any]]:
    """Score observations using viewport-relative temperature and vegetation ranks."""
    if not math.isfinite(temperature_weight) or not 0 <= temperature_weight <= 1:
        raise ValueError("temperature_weight must be between 0 and 1")
    vegetation_weight = 1 - temperature_weight

    temperatures: list[float | None] = []
    vegetation_indices: list[float | None] = []
    for sample in samples:
        temperature = sample.get("surface_temp_c")
        vegetation_index = sample.get("vegetation_index")
        temperatures.append(
            float(temperature)
            if isinstance(temperature, (int, float)) and math.isfinite(temperature)
            else None
        )
        vegetation_indices.append(
            float(vegetation_index)
            if isinstance(vegetation_index, (int, float))
            and math.isfinite(vegetation_index)
            else None
        )

    temperature_ranks = _percentile_ranks(temperatures)
    vegetation_ranks = _percentile_ranks(vegetation_indices)
    scored_samples: list[dict[str, Any]] = []

    for sample, temperature_rank, vegetation_rank in zip(
        samples, temperature_ranks, vegetation_ranks
    ):
        temperature_factor = (
            temperature_rank * 100 if temperature_rank is not None else None
        )
        vegetation_factor = (
            (1 - vegetation_rank) * 100 if vegetation_rank is not None else None
        )
        weighted_factors = [
            (temperature_factor, temperature_weight),
            (vegetation_factor, vegetation_weight),
        ]
        available_factors = [
            (score, weight)
            for score, weight in weighted_factors
            if score is not None and weight > 0
        ]
        weight_total = sum(weight for _, weight in available_factors)
        priority_score = (
            sum(score * weight for score, weight in available_factors) / weight_total
            if weight_total
            else None
        )

        scored_samples.append(
            {
                **sample,
                "temperature_factor_score": (
                    round(temperature_factor, 1)
                    if temperature_factor is not None
                    else None
                ),
                "vegetation_deficit_factor_score": (
                    round(vegetation_factor, 1)
                    if vegetation_factor is not None
                    else None
                ),
                "priority_score": (
                    round(priority_score, 1) if priority_score is not None else None
                ),
            }
        )

    return scored_samples
