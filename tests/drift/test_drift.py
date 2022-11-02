#  Author:   Niels Nuyttens  <niels@nannyml.com>
#  #
#  License: Apache Software License 2.0

"""Tests for Drift package."""
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects
import pytest

from nannyml.base import AbstractCalculator, AbstractCalculatorResult
from nannyml.chunk import CountBasedChunker, DefaultChunker, PeriodBasedChunker, SizeBasedChunker
from nannyml.drift.univariate import UnivariateDriftCalculator
from nannyml.exceptions import InvalidArgumentsException


@pytest.fixture
def sample_drift_data() -> pd.DataFrame:  # noqa: D103
    data = pd.DataFrame(pd.date_range(start='1/6/2020', freq='10min', periods=20 * 1008), columns=['timestamp'])
    data['week'] = data.timestamp.dt.isocalendar().week - 1
    data['period'] = 'reference'
    data.loc[data.week >= 11, ['period']] = 'analysis'
    # data[NML_METADATA_PERIOD_COLUMN_NAME] = data['period']  # simulate preprocessing
    np.random.seed(167)
    data['f1'] = np.random.randn(data.shape[0])
    data['f2'] = np.random.rand(data.shape[0])
    data['f3'] = np.random.randint(4, size=data.shape[0])
    data['f4'] = np.random.randint(20, size=data.shape[0])
    data['y_pred_proba'] = np.random.rand(data.shape[0])
    data['output'] = np.random.randint(2, size=data.shape[0])
    data['actual'] = np.random.randint(2, size=data.shape[0])

    # Rule 1b is the shifted feature, 75% 0 instead of 50%
    rule1a = {2: 0, 3: 1}
    rule1b = {2: 0, 3: 0}
    data.loc[data.week < 16, ['f3']] = data.loc[data.week < 16, ['f3']].replace(rule1a)
    data.loc[data.week >= 16, ['f3']] = data.loc[data.week >= 16, ['f3']].replace(rule1b)

    # Rule 2b is the shifted feature
    c1 = 'white'
    c2 = 'red'
    c3 = 'green'
    c4 = 'blue'

    rule2a = {
        0: c1,
        1: c1,
        2: c1,
        3: c1,
        4: c1,
        5: c2,
        6: c2,
        7: c2,
        8: c2,
        9: c2,
        10: c3,
        11: c3,
        12: c3,
        13: c3,
        14: c3,
        15: c4,
        16: c4,
        17: c4,
        18: c4,
        19: c4,
    }

    rule2b = {
        0: c1,
        1: c1,
        2: c1,
        3: c1,
        4: c1,
        5: c2,
        6: c2,
        7: c2,
        8: c2,
        9: c2,
        10: c3,
        11: c3,
        12: c3,
        13: c1,
        14: c1,
        15: c4,
        16: c4,
        17: c4,
        18: c1,
        19: c2,
    }

    data.loc[data.week < 16, ['f4']] = data.loc[data.week < 16, ['f4']].replace(rule2a)
    data.loc[data.week >= 16, ['f4']] = data.loc[data.week >= 16, ['f4']].replace(rule2b)

    data.loc[data.week >= 16, ['f1']] = data.loc[data.week >= 16, ['f1']] + 0.6
    data.loc[data.week >= 16, ['f2']] = np.sqrt(data.loc[data.week >= 16, ['f2']])
    data.drop(columns=['week'], inplace=True)

    data['f3'] = data['f3'].astype("category")

    return data


@pytest.fixture
def sample_drift_data_with_nans(sample_drift_data) -> pd.DataFrame:  # noqa: D103
    data = sample_drift_data.copy(deep=True)
    data['id'] = data.index
    nan_pick1 = set(data.id.sample(frac=0.11, random_state=13))
    nan_pick2 = set(data.id.sample(frac=0.11, random_state=14))
    data.loc[data.id.isin(nan_pick1), 'f1'] = np.NaN
    data.loc[data.id.isin(nan_pick2), 'f4'] = np.NaN
    data.drop(columns=['id'], inplace=True)
    return data


class SimpleDriftResult(AbstractCalculatorResult):
    """Dummy DriftResult implementation."""

    def __init__(self, results_data: pd.DataFrame, calculator: AbstractCalculator):
        super().__init__(results_data)
        self.calculator = calculator

    @property
    def calculator_name(self) -> str:
        return "dummy_calculator"

    def plot(self, *args, **kwargs) -> Optional[plotly.graph_objects.Figure]:
        """Fake plot."""
        pass

    def _filter(self, period: str, metrics: List[str] = None, *args, **kwargs) -> AbstractCalculatorResult:
        pass


class SimpleDriftCalculator(AbstractCalculator):
    """Dummy DriftCalculator implementation that returns a DataFrame with the selected feature columns, no rows."""

    def _fit(self, reference_data: pd.DataFrame, *args, **kwargs):  # noqa: D102
        return self

    def _calculate(self, data: pd.DataFrame, *args, **kwargs) -> SimpleDriftResult:  # noqa: D102
        return SimpleDriftResult(results_data=data, calculator=self)


def test_base_drift_calculator_uses_size_based_chunker_when_given_chunk_size(  # noqa: D103
    sample_drift_data,
):
    calc = SimpleDriftCalculator(chunk_size=1000)
    assert isinstance(calc.chunker, SizeBasedChunker)
    assert calc.chunker.chunk_size == 1000


def test_base_drift_calculator_uses_count_based_chunker_when_given_chunk_number(sample_drift_data):  # noqa: D103
    calc = SimpleDriftCalculator(chunk_number=1000)
    assert isinstance(calc.chunker, CountBasedChunker)
    assert calc.chunker.chunk_number == 1000


def test_base_drift_calculator_uses_period_based_chunker_when_given_chunk_period(sample_drift_data):  # noqa: D103
    calc = SimpleDriftCalculator(chunk_period='W')
    assert isinstance(calc.chunker, PeriodBasedChunker)
    assert calc.chunker.offset == 'W'


def test_base_drift_calculator_uses_default_chunker_when_no_chunker_specified(sample_drift_data):  # noqa: D103
    calc = SimpleDriftCalculator()
    assert isinstance(calc.chunker, DefaultChunker)


@pytest.mark.parametrize(
    'chunker',
    [
        (PeriodBasedChunker(offset='W', timestamp_column_name='timestamp')),
        (PeriodBasedChunker(offset='M', timestamp_column_name='timestamp')),
        (SizeBasedChunker(chunk_size=1000)),
        CountBasedChunker(chunk_number=25),
    ],
    ids=['chunk_period_weekly', 'chunk_period_monthly', 'chunk_size_1000', 'chunk_count_25'],
)
def test_univariate_drift_calculator_should_return_a_row_for_each_analysis_chunk_key(  # noqa: D103
    sample_drift_data, chunker
):
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
        chunker=chunker,
    ).fit(ref_data)
    sut = calc.calculate(data=sample_drift_data).filter(period='analysis').data

    chunks = chunker.split(sample_drift_data)
    assert len(chunks) == sut.shape[0]
    chunk_keys = [c.key for c in chunks]
    assert ('chunk', 'chunk', 'key') in sut.columns
    assert sorted(chunk_keys) == sorted(sut[('chunk', 'chunk', 'key')].values)


def test_univariate_statistical_drift_calculator_should_contain_chunk_details(sample_drift_data):  # noqa: D103
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
    ).fit(ref_data)

    drift = calc.calculate(data=sample_drift_data)

    sut = drift.data.columns
    assert ('chunk', 'chunk', 'key') in sut
    assert ('chunk', 'chunk', 'start_index') in sut
    assert ('chunk', 'chunk', 'start_date') in sut
    assert ('chunk', 'chunk', 'end_index') in sut
    assert ('chunk', 'chunk', 'end_date') in sut


def test_univariate_statistical_drift_calculator_returns_stat_column_for_each_feature(  # noqa: D103
    sample_drift_data,
):
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
    ).fit(ref_data)

    sut = calc.calculate(data=sample_drift_data).data.columns

    for f in ['f1', 'f2']:
        assert (f, 'kolmogorov_smirnov', 'value') in sut

    for f in ['f3', 'f4']:
        assert (f, 'chi2', 'value') in sut


def test_statistical_drift_calculator_deals_with_missing_class_labels(sample_drift_data):  # noqa: D103
    # rig the data by setting all f3-values in first analysis chunk to 0
    sample_drift_data.loc[10080:16000, 'f3'] = 0
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    analysis_data = sample_drift_data.loc[sample_drift_data['period'] == 'analysis']
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
    ).fit(ref_data)
    results = calc.calculate(data=analysis_data)

    assert not np.isnan(results.data.loc[0, ('f3', 'chi2', 'value')])


@pytest.mark.parametrize(
    'calculator_opts, expected',
    [
        (
            {'chunk_size': 5000},
            [0.005067460317460304, 0.004932539682539705, 0.01185952380952382, 0.24206810631229236],
        ),
        (
            {'chunk_size': 5000, 'timestamp_column_name': 'timestamp'},
            [0.005067460317460304, 0.004932539682539705, 0.01185952380952382, 0.24206810631229236],
        ),
        (
            {'chunk_number': 5},
            [0.008829365079365048, 0.007886904761904734, 0.015178571428571375, 0.06502976190476184, 0.2535218253968254],
        ),
        (
            {'chunk_number': 5, 'timestamp_column_name': 'timestamp'},
            [0.008829365079365048, 0.007886904761904734, 0.015178571428571375, 0.06502976190476184, 0.2535218253968254],
        ),
        (
            {'chunk_period': 'M', 'timestamp_column_name': 'timestamp'},
            [
                0.007646520146520119,
                0.008035714285714257,
                0.009456605222734282,
                0.09057539682539684,
                0.25612599206349207,
            ],
        ),
        (
            {},
            [
                0.011011904761904723,
                0.01736111111111116,
                0.015773809523809523,
                0.011011904761904723,
                0.016865079365079305,
                0.01468253968253963,
                0.018650793650793696,
                0.11398809523809528,
                0.25496031746031744,
                0.2530753968253968,
            ],
        ),
        (
            {'timestamp_column_name': 'timestamp'},
            [
                0.011011904761904723,
                0.01736111111111116,
                0.015773809523809523,
                0.011011904761904723,
                0.016865079365079305,
                0.01468253968253963,
                0.018650793650793696,
                0.11398809523809528,
                0.25496031746031744,
                0.2530753968253968,
            ],
        ),
    ],
    ids=[
        'size_based_without_timestamp',
        'size_based_with_timestamp',
        'count_based_without_timestamp',
        'count_based_with_timestamp',
        'period_based_with_timestamp',
        'default_without_timestamp',
        'default_with_timestamp',
    ],
)
def test_univariate_statistical_drift_calculator_works_with_chunker(
    sample_drift_data, calculator_opts, expected  # noqa: D103
):
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
        **calculator_opts,
    ).fit(ref_data)
    sut = calc.calculate(data=sample_drift_data).filter(period='analysis').data

    assert all(sut[('f1', 'kolmogorov_smirnov', 'value')] == expected)


def test_statistical_drift_calculator_raises_type_error_when_features_missing():  # noqa: D103

    with pytest.raises(TypeError, match='column_names'):
        UnivariateDriftCalculator(timestamp_column_name='timestamp')


def test_statistical_drift_calculator_given_empty_reference_data_should_raise_invalid_args_exception(  # noqa: D103
    sample_drift_data,
):
    ref_data = pd.DataFrame(columns=sample_drift_data.columns)
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
    )
    with pytest.raises(InvalidArgumentsException):
        calc.fit(ref_data)


def test_base_drift_calculator_given_empty_analysis_data_should_raise_invalid_args_exception(  # noqa: D103
    sample_drift_data,
):
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f2', 'f3', 'f4'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
    ).fit(ref_data)
    with pytest.raises(InvalidArgumentsException):
        calc.calculate(data=pd.DataFrame(columns=sample_drift_data.columns))


def test_base_drift_calculator_given_non_empty_features_list_should_only_calculate_for_these_features(  # noqa: D103
    sample_drift_data,
):
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    ana_data = sample_drift_data.loc[sample_drift_data['period'] == 'analysis']

    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f3'],
        timestamp_column_name='timestamp',
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
    ).fit(ref_data)
    res = calc.calculate(data=ana_data)
    sut = list(set(res.data.columns.get_level_values(level=0)))

    assert 'f2' not in sut
    assert 'f4' not in sut


@pytest.mark.parametrize(
    'calc_args, plot_args',
    [
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'drift', 'plot_reference': False, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'},
        ),
        ({}, {'kind': 'drift', 'plot_reference': False, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'drift', 'plot_reference': True, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'},
        ),
        ({}, {'kind': 'drift', 'plot_reference': True, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'drift', 'plot_reference': False, 'column_name': 'f3', 'method': 'chi2'},
        ),
        ({}, {'kind': 'drift', 'plot_reference': False, 'column_name': 'f3', 'method': 'chi2'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'drift', 'plot_reference': True, 'column_name': 'f3', 'method': 'chi2'},
        ),
        ({}, {'kind': 'drift', 'plot_reference': True, 'column_name': 'f3', 'method': 'chi2'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'distribution', 'plot_reference': False, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'},
        ),
        ({}, {'kind': 'distribution', 'plot_reference': False, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'distribution', 'plot_reference': True, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'},
        ),
        ({}, {'kind': 'distribution', 'plot_reference': True, 'column_name': 'f1', 'method': 'kolmogorov_smirnov'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'distribution', 'plot_reference': False, 'column_name': 'f3', 'method': 'chi2'},
        ),
        ({}, {'kind': 'distribution', 'plot_reference': False, 'column_name': 'f3', 'method': 'chi2'}),
        (
            {'timestamp_column_name': 'timestamp'},
            {'kind': 'distribution', 'plot_reference': True, 'column_name': 'f3', 'method': 'chi2'},
        ),
        ({}, {'kind': 'distribution', 'plot_reference': True, 'column_name': 'f3', 'method': 'chi2'}),
    ],
    ids=[
        'continuous_feature_drift_with_timestamp_without_reference',
        'continuous_feature_drift_without_timestamp_without_reference',
        'continuous_feature_drift_with_timestamp_with_reference',
        'continuous_feature_drift_without_timestamp_with_reference',
        'categorical_feature_drift_with_timestamp_without_reference',
        'categorical_feature_drift_without_timestamp_without_reference',
        'categorical_feature_drift_with_timestamp_with_reference',
        'categorical_feature_drift_without_timestamp_with_reference',
        'continuous_feature_distribution_with_timestamp_without_reference',
        'continuous_feature_distribution_without_timestamp_without_reference',
        'continuous_feature_distribution_with_timestamp_with_reference',
        'continuous_feature_distribution_without_timestamp_with_reference',
        'categorical_feature_distribution_with_timestamp_without_reference',
        'categorical_feature_distribution_without_timestamp_without_reference',
        'categorical_feature_distribution_with_timestamp_with_reference',
        'categorical_feature_distribution_without_timestamp_with_reference',
    ],
)
def test_result_plots_raise_no_exceptions(sample_drift_data, calc_args, plot_args):  # noqa: D103
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    ana_data = sample_drift_data.loc[sample_drift_data['period'] == 'analysis']

    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f3'],
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
        **calc_args,
    ).fit(ref_data)
    sut = calc.calculate(data=ana_data)

    try:
        _ = sut.plot(**plot_args)
    except Exception as exc:
        pytest.fail(f"an unexpected exception occurred: {exc}")


def test_repeat_calculation_results_return_only_latest_calculation_results(sample_drift_data):
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    ana_data = sample_drift_data.loc[sample_drift_data['period'] == 'analysis']

    chunker = SizeBasedChunker(chunk_size=1000, timestamp_column_name='timestamp')
    analysis_chunks = chunker.split(ana_data)

    calc = UnivariateDriftCalculator(
        column_names=['f1', 'f3'],
        continuous_methods=['kolmogorov_smirnov'],
        categorical_methods=['chi2'],
        chunker=chunker,
        timestamp_column_name='timestamp',
    ).fit(ref_data)

    res0 = calc.calculate(analysis_chunks[0].data).filter(period='analysis')

    res1 = calc.calculate(analysis_chunks[1].data).filter(period='analysis')

    res2 = calc.calculate(analysis_chunks[2].data).filter(period='analysis')

    assert len(res0) == 1
    assert res0.data.loc[0, ('chunk', 'chunk', 'start_date')] == analysis_chunks[0].start_datetime
    assert res0.data.loc[0, ('chunk', 'chunk', 'end_date')] == analysis_chunks[0].end_datetime
    assert len(res1) == 1
    assert res1.data.loc[0, ('chunk', 'chunk', 'start_date')] == analysis_chunks[1].start_datetime
    assert res1.data.loc[0, ('chunk', 'chunk', 'end_date')] == analysis_chunks[1].end_datetime
    assert len(res2) == 1
    assert res2.data.loc[0, ('chunk', 'chunk', 'start_date')] == analysis_chunks[2].start_datetime
    assert res2.data.loc[0, ('chunk', 'chunk', 'end_date')] == analysis_chunks[2].end_datetime
