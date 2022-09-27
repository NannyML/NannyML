#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Calculates realized performance metrics when target data is available."""

from __future__ import annotations

import copy
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from nannyml._typing import ModelOutputsType, ProblemType
from nannyml.base import AbstractCalculator
from nannyml.chunk import Chunk, Chunker
from nannyml.exceptions import CalculatorNotFittedException, InvalidArgumentsException
from nannyml.performance_calculation.metrics.base import Metric, MetricFactory
from nannyml.performance_calculation.result import Result

TARGET_COMPLETENESS_RATE_COLUMN_NAME = 'NML_TARGET_INCOMPLETE'

SUPPORTED_METRICS = list(MetricFactory.registry.keys())


class PerformanceCalculator(AbstractCalculator):
    """Calculates realized performance metrics when target data is available."""

    def __init__(
        self,
        metrics: List[str],
        y_true: str,
        y_pred: str,
        problem_type: Union[str, ProblemType],
        y_pred_proba: ModelOutputsType = None,
        timestamp_column_name: str = None,
        chunk_size: int = None,
        chunk_number: int = None,
        chunk_period: str = None,
        chunker: Chunker = None,
    ):
        """Creates a new performance calculator.

        Parameters
        ----------
        y_true: str
            The name of the column containing target values.
        y_pred_proba: ModelOutputsType
            Name(s) of the column(s) containing your model output.
            Pass a single string when there is only a single model output column, e.g. in binary classification cases.
            Pass a dictionary when working with multiple output columns, e.g. in multiclass classification cases.
            The dictionary maps a class/label string to the column name containing model outputs for that class/label.
        y_pred: str
            The name of the column containing your model predictions.
        timestamp_column_name: str, default=None
            The name of the column containing the timestamp of the model prediction.
        metrics: List[str]
            A list of metrics to calculate.
        chunk_size: int, default=None
            Splits the data into chunks containing `chunks_size` observations.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunk_number: int, default=None
            Splits the data into `chunk_number` pieces.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunk_period: str, default=None
            Splits the data according to the given period.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunker : Chunker, default=None
            The `Chunker` used to split the data sets into a lists of chunks.

        Examples
        --------
        >>> import nannyml as nml
        >>>
        >>> reference_df, analysis_df, target_df = nml.load_synthetic_binary_classification_dataset()
        >>>
        >>> calc = nml.PerformanceCalculator(y_true='work_home_actual', y_pred='y_pred', y_pred_proba='y_pred_proba',
        >>>                                  timestamp_column_name='timestamp', metrics=['f1', 'roc_auc'])
        >>>
        >>> calc.fit(reference_df)
        >>>
        >>> results = calc.calculate(analysis_df.merge(target_df, on='identifier'))
        >>> print(results.data)
                     key  start_index  ...  roc_auc_upper_threshold roc_auc_alert
        0       [0:4999]            0  ...                  0.97866         False
        1    [5000:9999]         5000  ...                  0.97866         False
        2  [10000:14999]        10000  ...                  0.97866         False
        3  [15000:19999]        15000  ...                  0.97866         False
        4  [20000:24999]        20000  ...                  0.97866         False
        5  [25000:29999]        25000  ...                  0.97866          True
        6  [30000:34999]        30000  ...                  0.97866          True
        7  [35000:39999]        35000  ...                  0.97866          True
        8  [40000:44999]        40000  ...                  0.97866          True
        9  [45000:49999]        45000  ...                  0.97866          True
        >>> for metric in calc.metrics:
        >>>     results.plot(metric=metric, plot_reference=True).show()
        """
        super().__init__(chunk_size, chunk_number, chunk_period, chunker, timestamp_column_name)

        self.y_true = y_true
        self.y_pred = y_pred

        self.y_pred_proba = y_pred_proba

        if isinstance(problem_type, str):
            problem_type = ProblemType.parse(problem_type)
        self.problem_type = problem_type

        if self.problem_type is not ProblemType.REGRESSION and y_pred_proba is None:
            raise InvalidArgumentsException(f"'y_pred_proba' can not be 'None' for problem type {ProblemType.value}")

        self.metrics: List[Metric] = [
            MetricFactory.create(m, problem_type, {'calculator': self}) for m in metrics  # type: ignore
        ]

        self.previous_reference_data: Optional[pd.DataFrame] = None
        self.previous_reference_results: Optional[pd.DataFrame] = None

        self.result: Optional[Result] = None

    def __str__(self):
        return f"PerformanceCalculator[metrics={str(self.metrics)}]"

    def _fit(self, reference_data: pd.DataFrame, *args, **kwargs) -> PerformanceCalculator:
        """Fits the calculator on the reference data, calibrating it for further use on the full dataset."""
        if reference_data.empty:
            raise InvalidArgumentsException('reference data contains no rows. Provide a valid reference data set.')

        if self.y_true not in reference_data.columns:
            raise InvalidArgumentsException(
                f"target data column '{self.y_true}' not found in data columns: {reference_data.columns}."
            )

        reference_data = reference_data.copy()

        # data validation is performed during the _fit for each metric

        for metric in self.metrics:
            metric.fit(reference_data=reference_data, chunker=self.chunker)

        self.previous_reference_data = reference_data
        self.result = self._calculate(reference_data)
        self.result.data['period'] = 'reference'

        return self

    def _calculate(self, data: pd.DataFrame, *args, **kwargs) -> Result:
        """Calculates performance on the analysis data, using the metrics specified on calculator creation."""
        if data.empty:
            raise InvalidArgumentsException('data contains no rows. Please provide a valid data set.')

        if self.y_true not in data.columns:
            raise InvalidArgumentsException(f"data does not contain target data column '{self.y_true}'.")

        data = data.copy()

        # Setup for target completeness rate
        data['NML_TARGET_INCOMPLETE'] = data[self.y_true].isna().astype(np.int16)

        # Generate chunks
        if self.chunker is None:
            raise CalculatorNotFittedException(
                'chunker has not been set. '
                'Please ensure you run ``calculator.fit()`` '
                'before running ``calculator.calculate()``'
            )
        chunks = self.chunker.split(data)

        # Construct result frame
        res = pd.DataFrame.from_records(
            [
                {
                    'key': chunk.key,
                    'chunk_index': chunk.chunk_index,
                    'start_index': chunk.start_index,
                    'end_index': chunk.end_index,
                    'start_date': chunk.start_datetime,
                    'end_date': chunk.end_datetime,
                    'period': 'analysis' if chunk.is_transition else chunk.period,
                    'targets_missing_rate': chunk.data[TARGET_COMPLETENESS_RATE_COLUMN_NAME].sum()
                    / chunk.data[TARGET_COMPLETENESS_RATE_COLUMN_NAME].count(),
                    **self._calculate_metrics_for_chunk(chunk),
                }
                for chunk in chunks
            ]
        )

        res['period'] = 'analysis'
        if self.result is None:
            self.result = Result(results_data=res, calculator=copy.deepcopy(self))
        else:
            self.result.data = pd.concat([self.result.data, res])

        return self.result

    def _calculate_metrics_for_chunk(self, chunk: Chunk) -> Dict:
        metrics_results = {}
        for metric in self.metrics:
            chunk_metric = metric.calculate(chunk.data)
            metrics_results[metric.column_name] = chunk_metric
            metrics_results[f'{metric.column_name}_lower_threshold'] = metric.lower_threshold
            metrics_results[f'{metric.column_name}_upper_threshold'] = metric.upper_threshold
            metrics_results[f'{metric.column_name}_sampling_error'] = metric.sampling_error(chunk.data)
            metrics_results[f'{metric.column_name}_alert'] = (
                metric.lower_threshold > chunk_metric or chunk_metric > metric.upper_threshold
            )

        return metrics_results
