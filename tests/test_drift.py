#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Tests for Drift package."""

from typing import List

import numpy as np
import pandas as pd
import pytest

from nannyml.chunk import Chunk, CountBasedChunker, DefaultChunker, PeriodBasedChunker, SizeBasedChunker
from nannyml.drift import BaseDriftCalculator
from nannyml.drift.reconstruction_error_drift_calcutor import ReconstructionErrorDriftCalculator
from nannyml.drift.statistical_drift_calculator import StatisticalDriftCalculator, calculate_statistical_drift
from nannyml.exceptions import CalculatorException, InvalidArgumentsException
from nannyml.metadata import NML_METADATA_COLUMNS, FeatureType, extract_metadata


@pytest.fixture
def sample_drift_data() -> pd.DataFrame:  # noqa: D103
    data = pd.DataFrame(pd.date_range(start='1/6/2020', freq='10min', periods=20 * 1008), columns=['timestamp'])
    data['week'] = data.timestamp.dt.isocalendar().week - 1
    data['partition'] = 'reference'
    data.loc[data.week >= 11, ['partition']] = 'analysis'
    # data[NML_METADATA_PARTITION_COLUMN_NAME] = data['partition']  # simulate preprocessing
    np.random.seed(167)
    data['f1'] = np.random.randn(data.shape[0])
    data['f2'] = np.random.rand(data.shape[0])
    data['f3'] = np.random.randint(4, size=data.shape[0])
    data['f4'] = np.random.randint(20, size=data.shape[0])
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
    data['id'] = data.index
    data.drop(columns=['week'], inplace=True)

    return data


@pytest.fixture
def sample_drift_metadata(sample_drift_data):  # noqa: D103
    return extract_metadata(sample_drift_data, model_name='model')


class SimpleDriftCalculator(BaseDriftCalculator):
    """Dummy DriftCalculator implementation that returns a DataFrame with the selected feature columns, no rows."""

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _calculate_drift(
        self,
        chunks: List[Chunk],
    ) -> pd.DataFrame:
        df = chunks[0].data.drop(columns=NML_METADATA_COLUMNS)
        return pd.DataFrame(columns=df.columns)


def test_base_drift_calculator_given_empty_reference_data_should_raise_invalid_args_exception(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    ref_data = pd.DataFrame(columns=sample_drift_data.columns)
    calc = SimpleDriftCalculator(sample_drift_metadata)
    with pytest.raises(InvalidArgumentsException):
        calc.fit(ref_data)


def test_base_drift_calculator_given_empty_analysis_data_should_raise_invalid_args_exception(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = SimpleDriftCalculator(sample_drift_metadata)
    with pytest.raises(InvalidArgumentsException):
        calc.calculate(
            data=pd.DataFrame(columns=sample_drift_data.columns),
            chunker=SizeBasedChunker(chunk_size=1000, minimum_chunk_size=1),
        )


def test_base_drift_calculator_given_empty_features_list_should_calculate_for_all_features(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = SimpleDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(
        data=sample_drift_data,
        chunker=SizeBasedChunker(chunk_size=1000, minimum_chunk_size=1),
    )

    md = extract_metadata(sample_drift_data, model_name='model')
    assert len(sut.columns) == len(md.features)
    for f in md.features:
        assert f.column_name in sut.columns


def test_base_drift_calculator_given_non_empty_features_list_should_only_calculate_for_these_features(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = SimpleDriftCalculator(sample_drift_metadata, features=['f1', 'f3'])
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(
        data=sample_drift_data,
        chunker=SizeBasedChunker(chunk_size=1000, minimum_chunk_size=1),
    )
    sut = calc.calculate(
        data=sample_drift_data,
        chunker=SizeBasedChunker(chunk_size=1000, minimum_chunk_size=1),
    )
    assert len(sut.columns) == 2
    assert 'f1' in sut.columns
    assert 'f3' in sut.columns


def test_base_drift_calculator_uses_size_based_chunker_when_given_chunk_size(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    class TestDriftCalculator(BaseDriftCalculator):
        def _fit(self, reference_data: pd.DataFrame):
            pass

        def _calculate_drift(self, chunks: List[Chunk]) -> pd.DataFrame:
            chunk_keys = [c.key for c in chunks]
            return pd.DataFrame({'keys': chunk_keys})

    calc = TestDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(sample_drift_data, chunk_size=100)['keys']
    expected = [
        c.key
        for c in SizeBasedChunker(100, minimum_chunk_size=1).split(sample_drift_metadata.enrich(sample_drift_data))
    ]

    assert len(expected) == len(sut)
    assert sorted(expected) == sorted(sut)


def test_base_drift_calculator_uses_count_based_chunker_when_given_chunk_number(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    class TestDriftCalculator(BaseDriftCalculator):
        def _fit(self, reference_data: pd.DataFrame):
            pass

        def _calculate_drift(
            self,
            chunks: List[Chunk],
        ) -> pd.DataFrame:
            chunk_keys = [c.key for c in chunks]
            return pd.DataFrame({'keys': chunk_keys})

    calc = TestDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(sample_drift_data, chunk_number=100)['keys']

    assert 100 == len(sut)


def test_base_drift_calculator_uses_period_based_chunker_when_given_chunk_period(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    class TestDriftCalculator(BaseDriftCalculator):
        def _fit(self, reference_data: pd.DataFrame):
            pass

        def _calculate_drift(self, chunks: List[Chunk]) -> pd.DataFrame:
            chunk_keys = [c.key for c in chunks]
            return pd.DataFrame({'keys': chunk_keys})

    calc = TestDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(sample_drift_data, chunk_period='W')['keys']

    assert 20 == len(sut)


def test_base_drift_calculator_uses_default_chunker_when_no_chunker_specified(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    class TestDriftCalculator(BaseDriftCalculator):
        def _fit(self, reference_data: pd.DataFrame):
            pass

        def _calculate_drift(
            self,
            chunks: List[Chunk],
        ) -> pd.DataFrame:
            chunk_keys = [c.key for c in chunks]
            return pd.DataFrame({'keys': chunk_keys})

    calc = TestDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(sample_drift_data)['keys']
    expected = [
        c.key for c in DefaultChunker(minimum_chunk_size=300).split(sample_drift_metadata.enrich(sample_drift_data))
    ]

    assert len(expected) == len(sut)
    assert sorted(expected) == sorted(sut)


def test_base_drift_calculator_raises_calculator_exception_running_calculate_without_fitting(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = SimpleDriftCalculator(sample_drift_metadata)
    with pytest.raises(CalculatorException, match='missing value for `_minimum_chunk_size`.'):
        calc.calculate(sample_drift_data)


@pytest.mark.parametrize(
    'chunker',
    [
        (PeriodBasedChunker(offset='W', minimum_chunk_size=1)),
        (PeriodBasedChunker(offset='M', minimum_chunk_size=1)),
        (SizeBasedChunker(chunk_size=1000, minimum_chunk_size=1)),
        CountBasedChunker(chunk_count=25, minimum_chunk_size=1),
    ],
    ids=['chunk_period_weekly', 'chunk_period_monthly', 'chunk_size_1000', 'chunk_count_25'],
)
def test_statistical_drift_calculator_should_return_a_row_for_each_analysis_chunk_key(  # noqa: D103
    sample_drift_data, sample_drift_metadata, chunker
):
    calc = StatisticalDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(
        data=sample_drift_data,
        chunker=chunker,
    )

    chunks = chunker.split(sample_drift_metadata.enrich(sample_drift_data))
    assert len(chunks) == sut.shape[0]
    chunk_keys = [c.key for c in chunks]
    assert 'key' in sut.columns
    assert sorted(chunk_keys) == sorted(sut['key'].values)


def test_statistical_drift_calculator_should_contain_chunk_details(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = ReconstructionErrorDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)

    drift = calc.calculate(
        data=sample_drift_data,
        chunker=PeriodBasedChunker(offset='W', minimum_chunk_size=1),
    )

    sut = drift.columns
    assert 'key' in sut
    assert 'start_index' in sut
    assert 'start_date' in sut
    assert 'end_index' in sut
    assert 'end_date' in sut
    assert 'partition' in sut


def test_statistical_drift_calculator_should_return_a_stat_column_and_p_value_column_for_each_feature(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = StatisticalDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    sut = calc.calculate(
        data=sample_drift_data,
        chunker=SizeBasedChunker(chunk_size=1000, minimum_chunk_size=1),
    ).columns

    for f in sample_drift_metadata.features:
        if f.feature_type == FeatureType.CONTINUOUS:
            assert f'{f.column_name}_dstat' in sut
        else:
            assert f'{f.column_name}_chi2' in sut
        assert f'{f.column_name}_p_value' in sut


def test_statistical_drift_calculator(sample_drift_data, sample_drift_metadata):  # noqa: D103
    calc = StatisticalDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    analysis_data = sample_drift_data.loc[sample_drift_data['partition'] == 'analysis']
    calc.fit(ref_data)
    try:
        _ = calc.calculate(
            data=analysis_data,
            chunker=PeriodBasedChunker(offset='W', minimum_chunk_size=1),
        )
    except Exception:
        pytest.fail()


def test_calculate_statistical_drift_function_runs_on_defaults(sample_drift_data, sample_drift_metadata):  # noqa: D103
    reference_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']

    try:
        calculate_statistical_drift(reference_data, sample_drift_data, sample_drift_metadata)
    except Exception:
        pytest.fail()


def test_reconstruction_error_drift_calculator_with_params_should_not_fail(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = ReconstructionErrorDriftCalculator(sample_drift_metadata, n_components=0.75)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    try:
        drift = calc.calculate(
            data=sample_drift_data,
            chunker=PeriodBasedChunker(offset='W', minimum_chunk_size=1),
        )
        print(drift)
    except Exception:
        pytest.fail()


def test_reconstruction_error_drift_calculator_with_default_params_should_not_fail(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = ReconstructionErrorDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)
    try:
        drift = calc.calculate(
            data=sample_drift_data,
            chunker=PeriodBasedChunker(offset='W', minimum_chunk_size=1),
        )
        print(drift)
    except Exception:
        pytest.fail()


def test_reconstruction_error_drift_calculator_should_contain_chunk_details_and_single_drift_value_column(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = ReconstructionErrorDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)

    drift = calc.calculate(
        data=sample_drift_data,
        chunker=PeriodBasedChunker(offset='W', minimum_chunk_size=1),
    )

    sut = drift.columns
    assert len(sut) == 8
    assert 'key' in sut
    assert 'start_index' in sut
    assert 'start_date' in sut
    assert 'end_index' in sut
    assert 'end_date' in sut
    assert 'partition' in sut
    assert 'alert' in sut
    assert 'reconstruction_error' in sut


def test_reconstruction_error_drift_calculator_should_contain_a_row_for_each_chunk(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = ReconstructionErrorDriftCalculator(sample_drift_metadata)
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    calc.fit(ref_data)

    drift = calc.calculate(
        data=sample_drift_data,
        chunker=PeriodBasedChunker(offset='W', minimum_chunk_size=1),
    )

    sample_drift_data = sample_drift_metadata.enrich(sample_drift_data)
    expected = len(PeriodBasedChunker(offset='W', minimum_chunk_size=1).split(sample_drift_data))
    sut = len(drift)
    assert sut == expected


# TODO: find a better way to test this
def test_reconstruction_error_drift_calculator_should_not_fail_when_using_feature_subset(  # noqa: D103
    sample_drift_data, sample_drift_metadata
):
    calc = ReconstructionErrorDriftCalculator(model_metadata=sample_drift_metadata, features=['f1', 'f4'])
    ref_data = sample_drift_data.loc[sample_drift_data['partition'] == 'reference']
    try:
        calc.fit(ref_data)
        calc.calculate(sample_drift_data)
    except Exception as exc:
        pytest.fail(f"should not have failed but got {exc}")
