#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Unit tests for drift ranking."""
import copy

import pandas as pd
import pytest

from nannyml.datasets import (
    load_synthetic_binary_classification_dataset,
    load_synthetic_multiclass_classification_dataset,
    load_synthetic_car_price_dataset
)
from nannyml.drift.ranking import Ranker, AlertCountRanking, CorrelationRanking
from nannyml.drift.univariate import UnivariateDriftCalculator
from nannyml.drift.univariate import Result as UnivariateResults
from nannyml.performance_estimation.confidence_based.cbpe import CBPE
from nannyml.performance_estimation.direct_loss_estimation.dle import DLE
from nannyml.performance_estimation.confidence_based.results import Result as CBPEResults
from nannyml.performance_estimation.direct_loss_estimation.result import Result as DLEResults
from nannyml.performance_calculation.result import Result as PerformanceCalculationResults
from nannyml.performance_calculation.calculator import PerformanceCalculator
from nannyml.exceptions import InvalidArgumentsException


@pytest.fixture(scope='module')
def sample_drift_result() -> UnivariateResults:  # noqa: D103
    reference, analysis, _ = load_synthetic_binary_classification_dataset()
    calc = UnivariateDriftCalculator(
        timestamp_column_name='timestamp',
        column_names=[
            col for col in reference.columns if col not in ['timestamp', 'identifier', 'work_home_actual', 'period']
        ],
        continuous_methods=['kolmogorov_smirnov', 'jensen_shannon'],
        categorical_methods=['chi2', 'jensen_shannon'],
        chunk_size=5000,
    ).fit(reference)
    result = calc.calculate(analysis)
    return result


@pytest.fixture(scope='module')
def sample_realized_perf_result() -> PerformanceCalculationResults:  # noqa: D103
    reference, analysis, analysis_target = load_synthetic_binary_classification_dataset()
    analysis = analysis.merge(analysis_target, on='identifier')
    
    # initialize, fit and calculate realized performance
    realized = PerformanceCalculator(
        y_pred_proba='y_pred_proba',
        y_pred='y_pred',
        y_true='work_home_actual',
        timestamp_column_name='timestamp',
        problem_type='classification_binary',
        metrics=['roc_auc', 'f1'],
        chunk_size=5000)
    realized.fit(reference)
    realized_performance = realized.calculate(analysis)
    return realized_performance


@pytest.fixture(scope='module')
def sample_multiclass_realized_perf_result() -> PerformanceCalculationResults:  # noqa: D103
    reference, analysis, analysis_target = load_synthetic_multiclass_classification_dataset()
    analysis = analysis.merge(analysis_target, on='identifier')
    # initialize, fit and calculate realized performance
    realized = PerformanceCalculator(
        y_pred_proba={
            'prepaid_card': 'y_pred_proba_prepaid_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'upmarket_card': 'y_pred_proba_upmarket_card'
        },
        y_pred='y_pred',
        y_true='y_true',
        timestamp_column_name='timestamp',
        problem_type='classification_multiclass',
        metrics=['roc_auc', 'f1'],
        chunk_size=6000)
    realized.fit(reference)
    realized_performance = realized.calculate(analysis)
    return realized_performance

@pytest.fixture(scope='module')
def sample_multiclass_estimated_perf_result() -> PerformanceCalculationResults:  # noqa: D103
    reference, analysis, analysis_target = load_synthetic_multiclass_classification_dataset()
    analysis = analysis.merge(analysis_target, on='identifier')
    # initialize, fit and calculate realized performance
    estimated = CBPE(
        y_pred_proba={
            'prepaid_card': 'y_pred_proba_prepaid_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'upmarket_card': 'y_pred_proba_upmarket_card'
        },
        y_pred='y_pred',
        y_true='y_true',
        timestamp_column_name='timestamp',
        problem_type='classification_multiclass',
        metrics=['roc_auc', 'f1'],
        chunk_size=6000)
    estimated.fit(reference)
    estimated_performance = estimated.estimate(analysis)
    return estimated_performance


@pytest.fixture(scope='module')
def sample_multiclass_drift_result() -> UnivariateResults:  # noqa: D103
    reference, analysis, _ = load_synthetic_multiclass_classification_dataset()
    calc = UnivariateDriftCalculator(
        timestamp_column_name='timestamp',
        column_names=[
            'acq_channel',
            'app_behavioral_score',
            'requested_credit_limit',
            'app_channel',
            'credit_bureau_score',
            'stated_income',
            'is_customer',
        ],
        continuous_methods=['kolmogorov_smirnov', 'jensen_shannon'],
        categorical_methods=['chi2', 'jensen_shannon'],
        chunk_size=6000,
    ).fit(reference)
    result = calc.calculate(analysis)
    return result


@pytest.fixture(scope='module')
def sample_regression_drift_result() -> UnivariateResults:  # noqa: D103
    reference, analysis, _ = load_synthetic_car_price_dataset()
    calc = UnivariateDriftCalculator(
        timestamp_column_name='timestamp',
        column_names=[
            'car_age',
            'km_driven',
            'price_new',
            'accident_count',
            'door_count',
            'fuel',
            'transmission'
        ],
        continuous_methods=['kolmogorov_smirnov', 'jensen_shannon'],
        categorical_methods=['chi2', 'jensen_shannon'],
        chunk_size=6000,
    ).fit(reference)
    result = calc.calculate(analysis)
    return result


@pytest.fixture(scope='module')
def sample_regression_estimated_perf_result() -> PerformanceCalculationResults:  # noqa: D103
    reference, analysis, _ = load_synthetic_car_price_dataset()
    # initialize, fit and calculate realized performance
    estimated = DLE(
        feature_column_names=['car_age', 'km_driven', 'price_new', 'accident_count', 'door_count', 'fuel', 'transmission'],
        y_pred='y_pred',
        y_true='y_true',
        timestamp_column_name='timestamp',
        metrics=['rmse', 'rmsle'],
        chunk_size=6000,
        tune_hyperparameters=False
    )
    estimated.fit(reference)
    estimated_performance = estimated.estimate(analysis)
    return estimated_performance


@pytest.fixture(scope='module')
def sample_regression_realized_perf_result() -> PerformanceCalculationResults:  # noqa: D103
    reference, analysis, analysis_target = load_synthetic_car_price_dataset()
    analysis = analysis.join(analysis_target)
    # initialize, fit and calculate realized performance
    calc = PerformanceCalculator(
        y_pred='y_pred',
        y_true='y_true',
        timestamp_column_name='timestamp',
        problem_type='regression',
        metrics=['rmse', 'rmsle'],
        chunk_size=6000)
    calc.fit(reference)
    realized_performance = calc.calculate(analysis)
    return realized_performance


def test_alertcount_ranker_creation():
    ranker = Ranker.by('alert_count')
    assert isinstance(ranker, AlertCountRanking)


def test_correlation_ranker_creation():
    ranker = Ranker.by('correlation')
    assert isinstance(ranker, CorrelationRanking)


def test_alert_count_ranking_raises_invalid_arguments_exception_when_drift_result_is_empty(
    sample_drift_result,
):  # noqa: D103
    ranking = AlertCountRanking()
    result = copy.deepcopy(sample_drift_result).filter(methods=['jensen_shannon'])
    result.data = pd.DataFrame(columns=['f1', 'f2', 'f3', 'f4'])
    with pytest.raises(InvalidArgumentsException, match='drift results contain no data'):
        ranking.rank(result)


def test_alert_count_ranking_contains_rank_column(sample_drift_result):  # noqa: D103
    ranking = AlertCountRanking()
    sut = ranking.rank(sample_drift_result)
    assert 'rank' in sut.columns


def test_alert_count_ranks_by_sum_of_alerts_per_feature(sample_drift_result):  # noqa: D103
    ranking = AlertCountRanking()
    sut = ranking.rank(sample_drift_result.filter(methods=['jensen_shannon']))
    assert sut.loc[sut['rank'] == 1, 'column_name'].values[0] == 'y_pred_proba'
    assert sut.loc[sut['rank'] == 2, 'column_name'].values[0] == 'wfh_prev_workday'
    assert sut.loc[sut['rank'] == 3, 'column_name'].values[0] == 'salary_range'
    assert sut.loc[sut['rank'] == 4, 'column_name'].values[0] == 'public_transportation_cost'


def test_alert_count_ranking_should_exclude_zero_alert_features_when_exclude_option_set(  # noqa: D103
    sample_drift_result,
):
    ranking = AlertCountRanking()
    sut = ranking.rank(sample_drift_result.filter(methods=['jensen_shannon']), only_drifting=True)
    assert len(sut) == 5
    assert not any(sut['column_name'] == 'gas_price_per_litre')


def test_alert_count_ranking_contains_rank_column(sample_drift_result):  # noqa: D103
    ranking = AlertCountRanking()
    sut = ranking.rank(sample_drift_result)
    assert 'rank' in sut.columns


def test_correlation_ranking_contains_rank_column(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    sut = ranking.rank(
        sample_drift_result.filter(period='all', methods=['jensen_shannon']),
        sample_realized_perf_result.filter(period='all', metrics=['roc_auc']))
    assert 'rank' in sut.columns


def test_correlation_ranking_raises_multiple_categorical_drift_metrics(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )

    with pytest.raises(
        ValueError,
        match='Only one categorical drift method should be present in the univariate results.'
    ):
        ranking.rank(
            sample_drift_result.filter(period='all', methods=['chi2', 'jensen_shannon']),
            sample_realized_perf_result.filter(period='all', metrics=['roc_auc'])
        )


def test_correlation_ranking_raises_multiple_continuous_drift_metrics(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )

    with pytest.raises(
        ValueError,
        match='Only one continuous drift method should be present in the univariate results.'
    ):
        ranking.rank(
            sample_drift_result.filter(period='all', methods=['kolmogorov_smirnov', 'jensen_shannon']),
            sample_realized_perf_result.filter(period='all', metrics=['roc_auc'])
        )


def test_correlation_ranking_raises_same_data_period(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    with pytest.raises(
        ValueError,
        match='Drift and Performance results need to be filtered to the same data period.'
    ):
        ranking.rank(
            sample_drift_result.filter(period='all', methods=['jensen_shannon']),
            sample_realized_perf_result.filter(period='analysis', metrics=['roc_auc'])
        )


def test_correlation_ranking_fit_raises_multiple_metrics(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    with pytest.raises(
        ValueError,
        match='Only one metric should be present in performance_results used to fit CorrelationRanking.'
    ):
        ranking.fit(
            performance_results=sample_realized_perf_result.filter(period='reference')
        )


def test_correlation_ranking_rank_raises_multiple_metrics(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    with pytest.raises(
        ValueError,
        match='Only one metric should be present in performance_results used to rank CorrelationRanking.'
    ):
        ranking.rank(
            sample_drift_result.filter(period='all', methods=['jensen_shannon']),
            sample_realized_perf_result.filter(period='all')
        )


def test_correlation_ranking_rank_raises_different_metrics(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    with pytest.raises(
        ValueError,
        match='Performance results need to be filtered with the same metric for fit and rank methods of Correlation Ranker.'
    ):
        ranking.rank(
            sample_drift_result.filter(period='all', methods=['jensen_shannon']),
            sample_realized_perf_result.filter(period='all', metrics=['f1'])
        )


def test_correlation_ranking_rank_raises_fit_error(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    with pytest.raises(
        ValueError,
        match='CorrelationRanking needs to call fit method before rank.'
    ):
        ranking.rank(
            sample_drift_result.filter(period='all', methods=['jensen_shannon']),
            sample_realized_perf_result.filter(period='all', metrics=['roc_auc'])
        )

def test_correlation_ranking_ranks_as_expected(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    sut = ranking.rank(
        sample_drift_result.filter(
            period='all',
            methods=['jensen_shannon'],
            column_names=[
                'distance_from_office', 'salary_range', 'gas_price_per_litre', 'public_transportation_cost',
                'wfh_prev_workday', 'workday', 'tenure'
            ]
        ),
        sample_realized_perf_result.filter(period='all', metrics=['roc_auc'])
    )
    print(sut)
    assert sut.loc[sut['rank'] == 1, 'column_name'].values[0] == 'wfh_prev_workday'
    assert sut.loc[sut['rank'] == 2, 'column_name'].values[0] == 'public_transportation_cost'
    assert sut.loc[sut['rank'] == 3, 'column_name'].values[0] == 'salary_range'
    assert sut.loc[sut['rank'] == 4, 'column_name'].values[0] == 'distance_from_office'


def test_correlation_ranking_ranks_as_expected(sample_drift_result, sample_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    sut = ranking.rank(
        sample_drift_result.filter(
            period='all',
            methods=['jensen_shannon'],
            column_names=[
                'distance_from_office', 'salary_range', 'gas_price_per_litre', 'public_transportation_cost',
                'wfh_prev_workday', 'workday', 'tenure'
            ]
        ),
        sample_realized_perf_result.filter(period='all', metrics=['roc_auc'])
    )
    print(sut)
    assert sut.loc[sut['rank'] == 1, 'column_name'].values[0] == 'wfh_prev_workday'
    assert sut.loc[sut['rank'] == 2, 'column_name'].values[0] == 'public_transportation_cost'
    assert sut.loc[sut['rank'] == 3, 'column_name'].values[0] == 'salary_range'
    assert sut.loc[sut['rank'] == 4, 'column_name'].values[0] == 'distance_from_office'


def test_correlation_ranking_contains_rank_column_multiclass_realized(sample_multiclass_drift_result, sample_multiclass_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_multiclass_realized_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    sut = ranking.rank(
        sample_multiclass_drift_result.filter(period='all', methods=['jensen_shannon']),
        sample_multiclass_realized_perf_result.filter(period='all', metrics=['roc_auc']))
    assert 'rank' in sut.columns


def test_correlation_ranking_contains_rank_column_multiclass_estimated(sample_multiclass_drift_result, sample_multiclass_estimated_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_multiclass_estimated_perf_result.filter(period='reference', metrics=['roc_auc'])
    )
    sut = ranking.rank(
        sample_multiclass_drift_result.filter(period='all', methods=['jensen_shannon']),
        sample_multiclass_estimated_perf_result.filter(period='all', metrics=['roc_auc']))
    assert 'rank' in sut.columns


def test_correlation_ranking_contains_rank_column_regression_realized(sample_regression_drift_result, sample_regression_realized_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_regression_realized_perf_result.filter(period='reference', metrics=['rmse'])
    )
    sut = ranking.rank(
        sample_regression_drift_result.filter(period='all', methods=['jensen_shannon']),
        sample_regression_realized_perf_result.filter(period='all', metrics=['rmse']))
    assert 'rank' in sut.columns


def test_correlation_ranking_contains_rank_column_regression_estimated(sample_regression_drift_result, sample_regression_estimated_perf_result):  # noqa: D103
    ranking = CorrelationRanking()
    ranking.fit(
        performance_results=sample_regression_estimated_perf_result.filter(period='reference', metrics=['rmse'])
    )
    sut = ranking.rank(
        sample_regression_drift_result.filter(period='all', methods=['jensen_shannon']),
        sample_regression_estimated_perf_result.filter(period='all', metrics=['rmse']))
    assert 'rank' in sut.columns
