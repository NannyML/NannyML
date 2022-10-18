import copy
from typing import List, Union

import pandas as pd
from plotly.graph_objects import Figure

from nannyml._typing import ProblemType
from nannyml.base import AbstractEstimator, AbstractEstimatorResult
from nannyml.exceptions import InvalidArgumentsException
from nannyml.performance_estimation.direct_loss_estimation.metrics import Metric, MetricFactory
from nannyml.plots import CHUNK_KEY_COLUMN_NAME
from nannyml.plots._step_plot import _step_plot


class Result(AbstractEstimatorResult):
    SUPPORTED_METRIC_VALUES = ['mae', 'mape', 'mse', 'rmse', 'msle', 'rmsle']

    def __init__(self, results_data: pd.DataFrame, estimator: AbstractEstimator):
        super().__init__(results_data)

        from .dle import DLE

        if not isinstance(estimator, DLE):
            raise RuntimeError(
                f"{estimator.__class__.__name__} is not an instance of type " f"DataReconstructionDriftCalculator"
            )
        self.estimator = estimator

    def _filter(self, period: str, metrics: List[str] = None, *args, **kwargs) -> AbstractEstimatorResult:
        columns = list(self.DEFAULT_COLUMNS)

        for metric in self.estimator.metrics:
            columns += [
                f'estimated_{metric.column_name}',
                f'upper_threshold_{metric.column_name}',
                f'lower_threshold_{metric.column_name}',
                f'alert_{metric.column_name}',
                f'sampling_error_{metric.column_name}',
            ]

        if period == 'all':
            data = self.data.loc[:, columns]
        else:
            data = self.data.loc[self.data['period'] == period, columns]

        data = data.reset_index(drop=True)

        return Result(results_data=data, estimator=copy.deepcopy(self.estimator))

    def plot(
        self,
        kind: str = 'performance',
        metric: Union[str, Metric] = None,
        plot_reference: bool = False,
        *args,
        **kwargs,
    ) -> Figure:
        if kind == 'performance':
            if metric is None:
                raise InvalidArgumentsException(
                    "no value for 'metric' given. Please provide the name of a metric to display."
                )
            if isinstance(metric, str):
                metric = MetricFactory.create(metric, ProblemType.REGRESSION, {'estimator': self.estimator})

            return _plot_direct_error_estimation_performance(self.data, metric, self.estimator, plot_reference)
        else:
            raise InvalidArgumentsException(f"unknown plot kind '{kind}'. " f"Please provide on of: ['performance'].")


def _plot_direct_error_estimation_performance(
    estimation_results: pd.DataFrame, metric: Metric, estimator, plot_reference: bool
) -> Figure:
    estimation_results = estimation_results.copy()

    plot_period_separator = plot_reference
    estimation_results['estimated'] = True

    if not plot_reference:
        estimation_results = estimation_results[estimation_results['period'] == 'analysis']

    # TODO: hack, assembling single results column to pass to plotting, overriding alert cols
    estimation_results['plottable'] = estimation_results.apply(
        lambda r: r[f'estimated_{metric.column_name}']
        if r['period'] == 'analysis'
        else r[f'realized_{metric.column_name}'],
        axis=1,
    )
    estimation_results['alert'] = estimation_results.apply(
        lambda r: r[f'alert_{metric.column_name}'] if r['period'] == 'analysis' else False, axis=1
    )

    is_time_based_x_axis = estimator.timestamp_column_name is not None

    # Plot estimated performance
    fig = _step_plot(
        table=estimation_results,
        metric_column_name='plottable',
        chunk_column_name=CHUNK_KEY_COLUMN_NAME,
        start_date_column_name='start_date' if is_time_based_x_axis else None,
        end_date_column_name='end_date' if is_time_based_x_axis else None,
        chunk_legend_labels=[
            f'Reference period (realized {metric.display_name})',
            f'Analysis period (estimated {metric.display_name})',
        ],
        drift_column_name='alert',
        drift_legend_label='Degraded performance',
        hover_labels=['Chunk', f'{metric.display_name}', 'Target data'],
        hover_marker_labels=['Reference', 'No change', 'Change'],
        lower_threshold_column_name=f'lower_threshold_{metric.column_name}',
        upper_threshold_column_name=f'upper_threshold_{metric.column_name}',
        threshold_legend_label='Performance threshold',
        title=f'DLE - Estimated {metric.display_name}',
        y_axis_title=f'{metric.display_name}',
        v_line_separating_analysis_period=plot_period_separator,
        estimated_column_name='estimated',
        lower_confidence_column_name=f'lower_confidence_{metric.column_name}',
        upper_confidence_column_name=f'upper_confidence_{metric.column_name}',
        sampling_error_column_name=f'sampling_error_{metric.column_name}',
    )

    return fig
