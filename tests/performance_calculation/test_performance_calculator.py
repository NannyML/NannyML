#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Unit tests for the PerformanceCalculator."""
from typing import Tuple

import numpy as np
import pandas as pd
import pytest

from nannyml._typing import ProblemType
from nannyml.datasets import (
    load_synthetic_binary_classification_dataset,
    load_synthetic_car_price_dataset,
    load_synthetic_multiclass_classification_dataset,
)
from nannyml.exceptions import InvalidArgumentsException
from nannyml.performance_calculation import PerformanceCalculator
from nannyml.performance_calculation.metrics.binary_classification import (
    BinaryClassificationAUROC,
    BinaryClassificationF1,
)


@pytest.fixture
def data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:  # noqa: D103
    ref_df, ana_df, tgt_df = load_synthetic_binary_classification_dataset()
    ref_df['y_pred'] = ref_df['y_pred_proba'].map(lambda p: p >= 0.8).astype(int)
    ana_df['y_pred'] = ana_df['y_pred_proba'].map(lambda p: p >= 0.8).astype(int)

    return ref_df, ana_df, tgt_df


@pytest.fixture()
def performance_calculator() -> PerformanceCalculator:
    return PerformanceCalculator(
        timestamp_column_name='timestamp',
        y_pred_proba='y_pred_proba',
        y_pred='y_pred',
        y_true='y_true',
        metrics=['roc_auc', 'f1'],
        problem_type='classification_binary',
    )


def test_calculator_init_with_empty_metrics_should_not_fail():  # noqa: D103, F821
    try:
        _ = PerformanceCalculator(
            timestamp_column_name='timestamp',
            y_pred='y_pred',
            y_pred_proba='y_pred_proba',
            y_true='y_true',
            metrics=[],
            problem_type='classification_binary',
        )
    except Exception as exc:
        pytest.fail(f'unexpected exception: {exc}')


def test_calculator_init_should_set_metrics(performance_calculator):  # noqa: D103
    calc = PerformanceCalculator(
        timestamp_column_name='timestamp',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        y_true='y_true',
        metrics=['roc_auc', 'f1'],
        problem_type='classification_binary',
    )
    sut = calc.metrics
    assert len(sut) == 2
    assert sut[0] == BinaryClassificationAUROC(calc)
    assert sut[1] == BinaryClassificationF1(calc)


def test_calculator_fit_should_raise_invalid_args_exception_when_no_target_data_present(data):  # noqa: D103, F821
    calc = PerformanceCalculator(
        timestamp_column_name='timestamp',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        y_true='y_true',
        metrics=['roc_auc', 'f1'],
        problem_type='classification_binary',
    )
    with pytest.raises(InvalidArgumentsException):
        _ = calc.fit(reference_data=data[0])


def test_calculator_calculate_should_raise_invalid_args_exception_when_no_target_data_present(data):  # noqa: D103, F821
    calc = PerformanceCalculator(
        timestamp_column_name='timestamp',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        y_true='work_home_actual',
        metrics=['roc_auc', 'f1'],
        problem_type='classification_binary',
    ).fit(reference_data=data[0])
    with pytest.raises(InvalidArgumentsException):
        _ = calc.calculate(data[1])


def test_calculator_calculate_should_include_chunk_information_columns(data):  # noqa: D103
    calc = PerformanceCalculator(
        timestamp_column_name='timestamp',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        y_true='work_home_actual',
        metrics=['roc_auc', 'f1'],
        problem_type='classification_binary',
    ).fit(reference_data=data[0])

    ref_with_tgt = data[1].merge(data[2], on='identifier')
    sut = calc.calculate(ref_with_tgt)

    assert 'key' in sut.data.columns
    assert 'start_index' in sut.data.columns
    assert 'end_index' in sut.data.columns
    assert 'start_date' in sut.data.columns
    assert 'end_date' in sut.data.columns
    assert 'period' in sut.data.columns


def test_calculator_calculate_should_include_target_completeness_rate(data):  # noqa: D103
    # Let's artificially modify the target completeness of different chunks.
    ref_data = data[0]
    data = data[1].merge(data[2], on='identifier')

    # Drop 10% of the target values in the first chunk
    data.loc[0:499, 'work_home_actual'] = np.NAN

    # Drop 90% of the target values in the second chunk
    data.loc[5000:9499, 'work_home_actual'] = np.NAN

    calc = PerformanceCalculator(
        timestamp_column_name='timestamp',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        y_true='work_home_actual',
        metrics=['roc_auc', 'f1'],
        problem_type='classification_binary',
    ).fit(reference_data=ref_data)
    result = calc.calculate(data)
    sut = result.data[result.data['period'] == 'analysis'].reset_index(drop=True)

    assert 'targets_missing_rate' in sut.columns
    assert sut.loc[0, 'targets_missing_rate'] == 0.1
    assert sut.loc[1, 'targets_missing_rate'] == 0.9


@pytest.mark.parametrize(
    'calc_args, plot_args',
    [
        ({'timestamp_column_name': 'timestamp'}, {'kind': 'performance', 'plot_reference': False, 'metric': 'mae'}),
        ({}, {'kind': 'performance', 'plot_reference': False, 'metric': 'mae'}),
        ({'timestamp_column_name': 'timestamp'}, {'kind': 'performance', 'plot_reference': True, 'metric': 'mae'}),
        ({}, {'kind': 'performance', 'plot_reference': True, 'metric': 'mae'}),
    ],
    ids=[
        'performance_with_timestamp_without_reference',
        'performance_without_timestamp_without_reference',
        'performance_with_timestamp_with_reference',
        'performance_without_timestamp_with_reference',
    ],
)
def test_regression_result_plots_raise_no_exceptions(calc_args, plot_args):  # noqa: D103
    reference, analysis, analysis_targets = load_synthetic_car_price_dataset()
    calc = PerformanceCalculator(
        y_true='y_true', y_pred='y_pred', problem_type=ProblemType.REGRESSION, metrics=['mae', 'mape'], **calc_args
    ).fit(reference)
    sut = calc.calculate(analysis.join(analysis_targets))

    try:
        _ = sut.plot(**plot_args)
    except Exception as exc:
        pytest.fail(f"an unexpected exception occurred: {exc}")


@pytest.mark.parametrize(
    'calc_args, plot_args',
    [
        ({'timestamp_column_name': 'timestamp'}, {'kind': 'performance', 'plot_reference': False, 'metric': 'f1'}),
        ({}, {'kind': 'performance', 'plot_reference': False, 'metric': 'f1'}),
        ({'timestamp_column_name': 'timestamp'}, {'kind': 'performance', 'plot_reference': True, 'metric': 'f1'}),
        ({}, {'kind': 'performance', 'plot_reference': True, 'metric': 'f1'}),
    ],
    ids=[
        'performance_with_timestamp_without_reference',
        'performance_without_timestamp_without_reference',
        'performance_with_timestamp_with_reference',
        'performance_without_timestamp_with_reference',
    ],
)
def test_multiclass_classification_result_plots_raise_no_exceptions(calc_args, plot_args):  # noqa: D103
    reference, analysis, analysis_targets = load_synthetic_multiclass_classification_dataset()
    calc = PerformanceCalculator(
        y_true='y_true',
        y_pred='y_pred',
        y_pred_proba={
            'upmarket_card': 'y_pred_proba_upmarket_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'prepaid_card': 'y_pred_proba_prepaid_card',
        },
        problem_type=ProblemType.CLASSIFICATION_MULTICLASS,
        metrics=['roc_auc', 'f1'],
        **calc_args,
    ).fit(reference)
    sut = calc.calculate(analysis.merge(analysis_targets, on='identifier'))

    try:
        _ = sut.plot(**plot_args)
    except Exception as exc:
        pytest.fail(f"an unexpected exception occurred: {exc}")


@pytest.mark.parametrize(
    'calc_args, plot_args',
    [
        ({'timestamp_column_name': 'timestamp'}, {'kind': 'performance', 'plot_reference': False, 'metric': 'f1'}),
        ({}, {'kind': 'performance', 'plot_reference': False, 'metric': 'f1'}),
        ({'timestamp_column_name': 'timestamp'}, {'kind': 'performance', 'plot_reference': True, 'metric': 'f1'}),
        ({}, {'kind': 'performance', 'plot_reference': True, 'metric': 'f1'}),
    ],
    ids=[
        'performance_with_timestamp_without_reference',
        'performance_without_timestamp_without_reference',
        'performance_with_timestamp_with_reference',
        'performance_without_timestamp_with_reference',
    ],
)
def test_binary_classification_result_plots_raise_no_exceptions(calc_args, plot_args):  # noqa: D103
    reference, analysis, analysis_targets = load_synthetic_binary_classification_dataset()
    calc = PerformanceCalculator(
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        problem_type=ProblemType.CLASSIFICATION_BINARY,
        metrics=['roc_auc', 'f1'],
        **calc_args,
    ).fit(reference)
    sut = calc.calculate(analysis.merge(analysis_targets, on='identifier'))

    try:
        _ = sut.plot(**plot_args)
    except Exception as exc:
        pytest.fail(f"an unexpected exception occurred: {exc}")
