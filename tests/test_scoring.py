import pytest

from heatlens.scoring import prioritize_samples


def test_priority_score_ranks_hot_and_sparse_vegetation_as_highest():
    samples = [
        {"surface_temp_c": 30.0, "vegetation_index": 0.7},
        {"surface_temp_c": 35.0, "vegetation_index": 0.4},
        {"surface_temp_c": 40.0, "vegetation_index": 0.1},
    ]

    scored = prioritize_samples(samples)

    assert [sample["priority_score"] for sample in scored] == [0, 50, 100]
    assert scored[2]["temperature_factor_score"] == 100
    assert scored[2]["vegetation_deficit_factor_score"] == 100


def test_temperature_weight_is_configurable_and_missing_factors_are_renormalized():
    samples = [
        {"surface_temp_c": 30.0, "vegetation_index": None},
        {"surface_temp_c": 40.0, "vegetation_index": None},
    ]

    scored = prioritize_samples(samples, temperature_weight=0.8)

    assert [sample["priority_score"] for sample in scored] == [0, 100]
    assert all(sample["vegetation_deficit_factor_score"] is None for sample in scored)


def test_changing_weight_changes_tradeoff_between_hot_and_sparse_vegetation():
    samples = [
        {"surface_temp_c": 40.0, "vegetation_index": 0.8},
        {"surface_temp_c": 30.0, "vegetation_index": 0.1},
    ]

    temperature_weighted = prioritize_samples(samples, temperature_weight=0.8)
    vegetation_weighted = prioritize_samples(samples, temperature_weight=0.2)

    assert temperature_weighted[0]["priority_score"] == 80
    assert vegetation_weighted[0]["priority_score"] == 20
    assert temperature_weighted[1]["priority_score"] == 20
    assert vegetation_weighted[1]["priority_score"] == 80


def test_equal_values_receive_neutral_percentile_scores():
    scored = prioritize_samples(
        [
            {"surface_temp_c": 35.0, "vegetation_index": 0.4},
            {"surface_temp_c": 35.0, "vegetation_index": 0.4},
        ]
    )

    assert [sample["priority_score"] for sample in scored] == [50, 50]


def test_samples_without_any_valid_inputs_receive_no_score():
    scored = prioritize_samples(
        [{"surface_temp_c": None, "vegetation_index": float("nan")}]
    )

    assert scored[0]["priority_score"] is None


@pytest.mark.parametrize("weight", [-0.01, 1.01, float("nan")])
def test_invalid_temperature_weight_is_rejected(weight):
    with pytest.raises(ValueError, match="temperature_weight"):
        prioritize_samples([], temperature_weight=weight)
