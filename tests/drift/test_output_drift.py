#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

import numpy as np
import pandas as pd
import pytest

from nannyml._typing import ProblemType
from nannyml.datasets import (
    load_synthetic_binary_classification_dataset,
    load_synthetic_car_price_dataset,
    load_synthetic_multiclass_classification_dataset,
)
from nannyml.drift.model_outputs.univariate.statistical import StatisticalOutputDriftCalculator


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


def test_output_drift_calculator_with_params_should_not_fail(sample_drift_data):  # noqa: D103
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = StatisticalOutputDriftCalculator(
        y_pred='output',
        y_pred_proba='y_pred_proba',
        timestamp_column_name='timestamp',
        chunk_period='W',
        problem_type=ProblemType.CLASSIFICATION_BINARY,
    ).fit(ref_data)
    try:
        _ = calc.calculate(data=sample_drift_data)
    except Exception:
        pytest.fail()


def test_output_drift_calculator_with_default_params_should_not_fail(sample_drift_data):  # noqa: D103
    ref_data = sample_drift_data.loc[sample_drift_data['period'] == 'reference']
    calc = StatisticalOutputDriftCalculator(
        y_pred='output',
        y_pred_proba='y_pred_proba',
        timestamp_column_name='timestamp',
        chunk_period='W',
        problem_type=ProblemType.CLASSIFICATION_BINARY,
    ).fit(ref_data)
    try:
        _ = calc.calculate(data=sample_drift_data)
    except Exception:
        pytest.fail()


def test_output_drift_calculator_for_regression_problems():  # noqa: D103
    reference, analysis, _ = load_synthetic_car_price_dataset()
    calc = StatisticalOutputDriftCalculator(
        y_pred='y_pred',
        timestamp_column_name='timestamp',
        chunk_size=5000,
        problem_type=ProblemType.REGRESSION,
    ).fit(reference)
    results = calc.calculate(analysis)

    assert (
        round(results.data['y_pred_dstat'], 5)
        == [0.01135, 0.01213, 0.00545, 0.01125, 0.01443, 0.00937, 0.2017, 0.2076, 0.21713, 0.19368, 0.21497, 0.21142]
    ).all()
    assert (
        round(results.data['y_pred_p_value'], 5)
        == [0.588, 0.501, 0.999, 0.599, 0.289, 0.809, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    ).all()


@pytest.mark.parametrize(
    'calculator_opts, expected',
    [
        (
            {'chunk_size': 10000},
            pd.DataFrame(
                {
                    'key': [
                        '[0:9999]',
                        '[10000:19999]',
                        '[20000:29999]',
                        '[30000:39999]',
                        '[40000:49999]',
                        '[50000:59999]',
                    ],
                    'y_pred_dstat': [
                        0.01046666666666668,
                        0.007200000000000012,
                        0.007183333333333319,
                        0.2041,
                        0.20484999999999998,
                        0.21286666666666665,
                    ],
                    'y_pred_p_value': [0.303, 0.763, 0.766, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_size': 10000, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': [
                        '[0:9999]',
                        '[10000:19999]',
                        '[20000:29999]',
                        '[30000:39999]',
                        '[40000:49999]',
                        '[50000:59999]',
                    ],
                    'y_pred_dstat': [
                        0.01046666666666668,
                        0.007200000000000012,
                        0.007183333333333319,
                        0.2041,
                        0.20484999999999998,
                        0.21286666666666665,
                    ],
                    'y_pred_p_value': [0.303, 0.763, 0.766, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_number': 5},
            pd.DataFrame(
                {
                    'key': ['[0:11999]', '[12000:23999]', '[24000:35999]', '[36000:47999]', '[48000:59999]'],
                    'y_pred_dstat': [
                        0.009250000000000008,
                        0.007400000000000018,
                        0.10435000000000001,
                        0.20601666666666663,
                        0.21116666666666667,
                    ],
                    'y_pred_p_value': [0.357, 0.641, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_number': 5, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['[0:11999]', '[12000:23999]', '[24000:35999]', '[36000:47999]', '[48000:59999]'],
                    'y_pred_dstat': [
                        0.009250000000000008,
                        0.007400000000000018,
                        0.10435000000000001,
                        0.20601666666666663,
                        0.21116666666666667,
                    ],
                    'y_pred_p_value': [0.357, 0.641, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_period': 'M', 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['2017-02', '2017-03'],
                    'y_pred_dstat': [0.010885590414630303, 0.20699588120912144],
                    'y_pred_p_value': [0.015, 0.0],
                }
            ),
        ),
        (
            {},
            pd.DataFrame(
                {
                    'key': [
                        '[0:5999]',
                        '[6000:11999]',
                        '[12000:17999]',
                        '[18000:23999]',
                        '[24000:29999]',
                        '[30000:35999]',
                        '[36000:41999]',
                        '[42000:47999]',
                        '[48000:53999]',
                        '[54000:59999]',
                    ],
                    'y_pred_dstat': [
                        0.009183333333333321,
                        0.016349999999999976,
                        0.01079999999999999,
                        0.010183333333333336,
                        0.01065000000000002,
                        0.20288333333333336,
                        0.20734999999999998,
                        0.20468333333333333,
                        0.20713333333333334,
                        0.21588333333333334,
                    ],
                    'y_pred_p_value': [0.743, 0.107, 0.544, 0.62, 0.562, 0.0, 0.0, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': [
                        '[0:5999]',
                        '[6000:11999]',
                        '[12000:17999]',
                        '[18000:23999]',
                        '[24000:29999]',
                        '[30000:35999]',
                        '[36000:41999]',
                        '[42000:47999]',
                        '[48000:53999]',
                        '[54000:59999]',
                    ],
                    'y_pred_dstat': [
                        0.009183333333333321,
                        0.016349999999999976,
                        0.01079999999999999,
                        0.010183333333333336,
                        0.01065000000000002,
                        0.20288333333333336,
                        0.20734999999999998,
                        0.20468333333333333,
                        0.20713333333333334,
                        0.21588333333333334,
                    ],
                    'y_pred_p_value': [0.743, 0.107, 0.544, 0.62, 0.562, 0.0, 0.0, 0.0, 0.0, 0.0],
                }
            ),
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
def test_univariate_statistical_drift_calculator_for_regression_works_with_chunker(
    calculator_opts, expected  # noqa: D103
):
    reference, analysis, _ = load_synthetic_car_price_dataset()
    calc = StatisticalOutputDriftCalculator(
        y_pred='y_pred',
        problem_type=ProblemType.REGRESSION,
        **calculator_opts,
    ).fit(reference)
    results = calc.calculate(analysis)

    pd.testing.assert_frame_equal(expected, results.data[['key', 'y_pred_dstat', 'y_pred_p_value']])


@pytest.mark.parametrize(
    'calculator_opts, expected',
    [
        (
            {'chunk_size': 10000},
            pd.DataFrame(
                {
                    'key': ['[0:9999]', '[10000:19999]', '[20000:29999]', '[30000:39999]', '[40000:49999]'],
                    'y_pred_chi2': [
                        0.860333803964031,
                        3.0721462648836715,
                        6.609667643816801,
                        19.49553770190838,
                        24.09326946563376,
                    ],
                    'y_pred_p_value': [0.354, 0.08, 0.01, 0.0, 0.0],
                    'y_pred_proba_dstat': [
                        0.009019999999999972,
                        0.011160000000000003,
                        0.07168000000000002,
                        0.1286,
                        0.12749999999999997,
                    ],
                    'y_pred_proba_p_value': [0.504, 0.249, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_size': 10000, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['[0:9999]', '[10000:19999]', '[20000:29999]', '[30000:39999]', '[40000:49999]'],
                    'y_pred_chi2': [
                        0.860333803964031,
                        3.0721462648836715,
                        6.609667643816801,
                        19.49553770190838,
                        24.09326946563376,
                    ],
                    'y_pred_p_value': [0.354, 0.08, 0.01, 0.0, 0.0],
                    'y_pred_proba_dstat': [
                        0.009019999999999972,
                        0.011160000000000003,
                        0.07168000000000002,
                        0.1286,
                        0.12749999999999997,
                    ],
                    'y_pred_proba_p_value': [0.504, 0.249, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_number': 5},
            pd.DataFrame(
                {
                    'key': ['[0:9999]', '[10000:19999]', '[20000:29999]', '[30000:39999]', '[40000:49999]'],
                    'y_pred_chi2': [
                        0.860333803964031,
                        3.0721462648836715,
                        6.609667643816801,
                        19.49553770190838,
                        24.09326946563376,
                    ],
                    'y_pred_p_value': [0.354, 0.08, 0.01, 0.0, 0.0],
                    'y_pred_proba_dstat': [
                        0.009019999999999972,
                        0.011160000000000003,
                        0.07168000000000002,
                        0.1286,
                        0.12749999999999997,
                    ],
                    'y_pred_proba_p_value': [0.504, 0.249, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_number': 5, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['[0:9999]', '[10000:19999]', '[20000:29999]', '[30000:39999]', '[40000:49999]'],
                    'y_pred_chi2': [
                        0.860333803964031,
                        3.0721462648836715,
                        6.609667643816801,
                        19.49553770190838,
                        24.09326946563376,
                    ],
                    'y_pred_p_value': [0.354, 0.08, 0.01, 0.0, 0.0],
                    'y_pred_proba_dstat': [
                        0.009019999999999972,
                        0.011160000000000003,
                        0.07168000000000002,
                        0.1286,
                        0.12749999999999997,
                    ],
                    'y_pred_proba_p_value': [0.504, 0.249, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_period': 'Y', 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['2017', '2018', '2019', '2020', '2021'],
                    'y_pred_chi2': [
                        7.70713490741521,
                        4.264683512119149,
                        14.259031460383845,
                        30.73593452676024,
                        0.12120817142905127,
                    ],
                    'y_pred_p_value': [0.006, 0.039, 0.0, 0.0, 0.728],
                    'y_pred_proba_dstat': [
                        0.0258059773828756,
                        0.010519551545707828,
                        0.09013549032688456,
                        0.12807136369707492,
                        0.46668,
                    ],
                    'y_pred_proba_p_value': [0.005, 0.153, 0.0, 0.0, 0.016],
                }
            ),
        ),
        (
            {},
            pd.DataFrame(
                {
                    'key': [
                        '[0:4999]',
                        '[5000:9999]',
                        '[10000:14999]',
                        '[15000:19999]',
                        '[20000:24999]',
                        '[25000:29999]',
                        '[30000:34999]',
                        '[35000:39999]',
                        '[40000:44999]',
                        '[45000:49999]',
                    ],
                    'y_pred_chi2': [
                        7.442382882761337,
                        1.800169196688272,
                        1.7285289531065517,
                        1.5896121630342237,
                        0.060895769836341554,
                        12.512106658022049,
                        11.393384406782644,
                        9.813531942242996,
                        3.786524136939082,
                        27.99003983833193,
                    ],
                    'y_pred_p_value': [0.006, 0.18, 0.189, 0.207, 0.805, 0.0, 0.001, 0.002, 0.052, 0.0],
                    'y_pred_proba_dstat': [
                        0.025300000000000045,
                        0.012299999999999978,
                        0.01641999999999999,
                        0.010580000000000034,
                        0.014080000000000037,
                        0.13069999999999998,
                        0.12729999999999997,
                        0.1311,
                        0.11969999999999997,
                        0.13751999999999998,
                    ],
                    'y_pred_proba_p_value': [0.006, 0.494, 0.17, 0.685, 0.325, 0.0, 0.0, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': [
                        '[0:4999]',
                        '[5000:9999]',
                        '[10000:14999]',
                        '[15000:19999]',
                        '[20000:24999]',
                        '[25000:29999]',
                        '[30000:34999]',
                        '[35000:39999]',
                        '[40000:44999]',
                        '[45000:49999]',
                    ],
                    'y_pred_chi2': [
                        7.442382882761337,
                        1.800169196688272,
                        1.7285289531065517,
                        1.5896121630342237,
                        0.060895769836341554,
                        12.512106658022049,
                        11.393384406782644,
                        9.813531942242996,
                        3.786524136939082,
                        27.99003983833193,
                    ],
                    'y_pred_p_value': [0.006, 0.18, 0.189, 0.207, 0.805, 0.0, 0.001, 0.002, 0.052, 0.0],
                    'y_pred_proba_dstat': [
                        0.025300000000000045,
                        0.012299999999999978,
                        0.01641999999999999,
                        0.010580000000000034,
                        0.014080000000000037,
                        0.13069999999999998,
                        0.12729999999999997,
                        0.1311,
                        0.11969999999999997,
                        0.13751999999999998,
                    ],
                    'y_pred_proba_p_value': [0.006, 0.494, 0.17, 0.685, 0.325, 0.0, 0.0, 0.0, 0.0, 0.0],
                }
            ),
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
def test_univariate_statistical_drift_calculator_for_binary_classification_works_with_chunker(
    calculator_opts, expected  # noqa: D103
):
    reference, analysis, _ = load_synthetic_binary_classification_dataset()
    calc = StatisticalOutputDriftCalculator(
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        problem_type=ProblemType.CLASSIFICATION_BINARY,
        **calculator_opts,
    ).fit(reference)
    results = calc.calculate(analysis)

    pd.testing.assert_frame_equal(
        expected, results.data[['key', 'y_pred_chi2', 'y_pred_p_value', 'y_pred_proba_dstat', 'y_pred_proba_p_value']]
    )


@pytest.mark.parametrize(
    'calculator_opts, expected',
    [
        (
            {'chunk_size': 10000},
            pd.DataFrame(
                {
                    'key': [
                        '[0:9999]',
                        '[10000:19999]',
                        '[20000:29999]',
                        '[30000:39999]',
                        '[40000:49999]',
                        '[50000:59999]',
                    ],
                    'y_pred_chi2': [
                        1.894844933794635,
                        1.007925369679508,
                        5.341968282280158,
                        228.5670714965706,
                        263.46933956608086,
                        228.68832812811945,
                    ],
                    'y_pred_p_value': [0.388, 0.604, 0.069, 0.0, 0.0, 0.0],
                    'y_pred_proba_upmarket_card_dstat': [
                        0.009450000000000014,
                        0.006950000000000012,
                        0.014050000000000007,
                        0.14831666666666665,
                        0.13885000000000003,
                        0.14631666666666668,
                    ],
                    'y_pred_proba_upmarket_card_p_value': [0.426, 0.799, 0.067, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_size': 10000, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': [
                        '[0:9999]',
                        '[10000:19999]',
                        '[20000:29999]',
                        '[30000:39999]',
                        '[40000:49999]',
                        '[50000:59999]',
                    ],
                    'y_pred_chi2': [
                        1.894844933794635,
                        1.007925369679508,
                        5.341968282280158,
                        228.5670714965706,
                        263.46933956608086,
                        228.68832812811945,
                    ],
                    'y_pred_p_value': [0.388, 0.604, 0.069, 0.0, 0.0, 0.0],
                    'y_pred_proba_upmarket_card_dstat': [
                        0.009450000000000014,
                        0.006950000000000012,
                        0.014050000000000007,
                        0.14831666666666665,
                        0.13885000000000003,
                        0.14631666666666668,
                    ],
                    'y_pred_proba_upmarket_card_p_value': [0.426, 0.799, 0.067, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_number': 5},
            pd.DataFrame(
                {
                    'key': ['[0:11999]', '[12000:23999]', '[24000:35999]', '[36000:47999]', '[48000:59999]'],
                    'y_pred_chi2': [
                        1.8853789747457756,
                        0.9860257560785328,
                        72.71926368401432,
                        306.95758434731476,
                        275.337354950812,
                    ],
                    'y_pred_p_value': [0.39, 0.611, 0.0, 0.0, 0.0],
                    'y_pred_proba_upmarket_card_dstat': [
                        0.0076166666666666605,
                        0.00876666666666659,
                        0.07696666666666666,
                        0.14246666666666666,
                        0.1448,
                    ],
                    'y_pred_proba_upmarket_card_p_value': [0.605, 0.423, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_number': 5, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['[0:11999]', '[12000:23999]', '[24000:35999]', '[36000:47999]', '[48000:59999]'],
                    'y_pred_chi2': [
                        1.8853789747457756,
                        0.9860257560785328,
                        72.71926368401432,
                        306.95758434731476,
                        275.337354950812,
                    ],
                    'y_pred_p_value': [0.39, 0.611, 0.0, 0.0, 0.0],
                    'y_pred_proba_upmarket_card_dstat': [
                        0.0076166666666666605,
                        0.00876666666666659,
                        0.07696666666666666,
                        0.14246666666666666,
                        0.1448,
                    ],
                    'y_pred_proba_upmarket_card_p_value': [0.605, 0.423, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'chunk_period': 'Y', 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['2020', '2021'],
                    'y_pred_chi2': [207.2554347384955, 6.288483345011454],
                    'y_pred_p_value': [0.0, 0.043],
                    'y_pred_proba_upmarket_card_dstat': [0.07220877811346088, 0.16619285714285714],
                    'y_pred_proba_upmarket_card_p_value': [0.0, 0.0],
                }
            ),
        ),
        (
            {},
            pd.DataFrame(
                {
                    'key': [
                        '[0:5999]',
                        '[6000:11999]',
                        '[12000:17999]',
                        '[18000:23999]',
                        '[24000:29999]',
                        '[30000:35999]',
                        '[36000:41999]',
                        '[42000:47999]',
                        '[48000:53999]',
                        '[54000:59999]',
                    ],
                    'y_pred_chi2': [
                        2.4199133518806706,
                        1.2633881212231448,
                        0.21170529003761418,
                        1.0459424531991828,
                        2.891011519973576,
                        131.23790859647167,
                        155.59305405725468,
                        182.00063726142486,
                        137.68526858822366,
                        164.40667669928519,
                    ],
                    'y_pred_p_value': [0.298, 0.532, 0.9, 0.593, 0.236, 0.0, 0.0, 0.0, 0.0, 0.0],
                    'y_pred_proba_upmarket_card_dstat': [
                        0.012283333333333368,
                        0.008450000000000013,
                        0.007866666666666688,
                        0.01261666666666661,
                        0.01261666666666661,
                        0.14679999999999999,
                        0.14471666666666666,
                        0.14096666666666668,
                        0.14205,
                        0.14755,
                    ],
                    'y_pred_proba_upmarket_card_p_value': [0.38, 0.828, 0.886, 0.347, 0.347, 0.0, 0.0, 0.0, 0.0, 0.0],
                }
            ),
        ),
        (
            {'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': [
                        '[0:5999]',
                        '[6000:11999]',
                        '[12000:17999]',
                        '[18000:23999]',
                        '[24000:29999]',
                        '[30000:35999]',
                        '[36000:41999]',
                        '[42000:47999]',
                        '[48000:53999]',
                        '[54000:59999]',
                    ],
                    'y_pred_chi2': [
                        2.4199133518806706,
                        1.2633881212231448,
                        0.21170529003761418,
                        1.0459424531991828,
                        2.891011519973576,
                        131.23790859647167,
                        155.59305405725468,
                        182.00063726142486,
                        137.68526858822366,
                        164.40667669928519,
                    ],
                    'y_pred_p_value': [0.298, 0.532, 0.9, 0.593, 0.236, 0.0, 0.0, 0.0, 0.0, 0.0],
                    'y_pred_proba_upmarket_card_dstat': [
                        0.012283333333333368,
                        0.008450000000000013,
                        0.007866666666666688,
                        0.01261666666666661,
                        0.01261666666666661,
                        0.14679999999999999,
                        0.14471666666666666,
                        0.14096666666666668,
                        0.14205,
                        0.14755,
                    ],
                    'y_pred_proba_upmarket_card_p_value': [0.38, 0.828, 0.886, 0.347, 0.347, 0.0, 0.0, 0.0, 0.0, 0.0],
                }
            ),
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
def test_univariate_statistical_drift_calculator_for_multiclass_classification_works_with_chunker(
    calculator_opts, expected  # noqa: D103
):
    reference, analysis, _ = load_synthetic_multiclass_classification_dataset()
    calc = StatisticalOutputDriftCalculator(
        y_pred='y_pred',
        y_pred_proba={
            'upmarket_card': 'y_pred_proba_upmarket_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'prepaid_card': 'y_pred_proba_prepaid_card',
        },
        problem_type=ProblemType.CLASSIFICATION_MULTICLASS,
        **calculator_opts,
    ).fit(reference)
    results = calc.calculate(analysis)

    pd.testing.assert_frame_equal(
        expected,
        results.data[
            [
                'key',
                'y_pred_chi2',
                'y_pred_p_value',
                'y_pred_proba_upmarket_card_dstat',
                'y_pred_proba_upmarket_card_p_value',
            ]
        ],
    )
