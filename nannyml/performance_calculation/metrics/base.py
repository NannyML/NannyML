#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0
import abc
import logging
from logging import Logger
from typing import Callable, Dict, List, Optional, Tuple, Type, Union

import numpy as np
import pandas as pd

from nannyml._typing import ProblemType
from nannyml.chunk import Chunk, Chunker
from nannyml.exceptions import InvalidArgumentsException


class Metric(abc.ABC):
    """A performance metric used to calculate realized model performance."""

    def __init__(
        self,
        name: str,
        y_true: str,
        y_pred: str,
        components: List[Tuple[str, str]],
        y_pred_proba: Optional[Union[str, Dict[str, str]]] = None,
        upper_threshold_limit: Optional[float] = None,
        lower_threshold_limit: Optional[float] = None,
        **kwargs,
    ):
        """Creates a new Metric instance.

        Parameters
        ----------
        components: List[Tuple[str, str]]
            A list of (display_name, column_name) tuples. The
            display_name is used for display purposes, while the
            column_name is used for column names in the output.
        upper_threshold_limit : float, default=None
            An optional upper threshold for the performance metric.
        lower_threshold_limit : float, default=None
            An optional lower threshold for the performance metric.
        """
        self.name: str = name

        self.y_true = y_true
        self.y_pred = y_pred
        self.y_pred_proba = y_pred_proba

        self.upper_threshold: Optional[float] = None
        self.lower_threshold: Optional[float] = None
        self.lower_threshold_limit: Optional[float] = lower_threshold_limit
        self.upper_threshold_limit: Optional[float] = upper_threshold_limit

        # A list of (display_name, column_name) tuples
        self.components: List[Tuple[str, str]] = components

    def fit(self, reference_data: pd.DataFrame, chunker: Chunker):
        """Fits a Metric on reference data.

        Parameters
        ----------
        reference_data: pd.DataFrame
            The reference data used for fitting. Must have target data available.
        chunker: Chunker
            The :class:`~nannyml.chunk.Chunker` used to split the reference data into chunks.
            This value is provided by the calling
            :class:`~nannyml.performance_calculation.calculator.PerformanceCalculator`.

        """
        self._fit(reference_data)

        # Calculate alert thresholds
        reference_chunks = chunker.split(
            reference_data,
        )
        self.lower_threshold, self.upper_threshold = self._calculate_alert_thresholds(
            reference_chunks=reference_chunks,
            lower_limit=self.lower_threshold_limit,
            upper_limit=self.upper_threshold_limit,
        )

        return

    def _fit(self, reference_data: pd.DataFrame):
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Metric and it must implement the _fit method"
        )

    def calculate(self, data: pd.DataFrame):
        """Calculates performance metrics on data.

        Parameters
        ----------
        data: pd.DataFrame
            The data to calculate performance metrics on. Requires presence of either the predicted labels or
            prediction scores/probabilities (depending on the metric to be calculated), as well as the target data.
        """
        return self._calculate(data)

    def _calculate(self, data: pd.DataFrame):
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Metric and it must implement the _calculate method"
        )

    def sampling_error(self, data: pd.DataFrame):
        """Calculates the sampling error with respect to the reference data for a given chunk of data.

        Parameters
        ----------
        data: pd.DataFrame
            The data to calculate the sampling error on, with respect to the reference data.

        Returns
        -------

        sampling_error: float
            The expected sampling error.

        """
        return self._sampling_error(data)

    def _sampling_error(self, data: pd.DataFrame):
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Metric and it must implement the _sampling_error method"
        )

    def _calculate_alert_thresholds(
        self,
        reference_chunks: List[Chunk],
        std_num: int = 3,
        lower_limit: Optional[float] = None,
        upper_limit: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[float]]:
        chunked_reference_metric = [self.calculate(chunk.data) for chunk in reference_chunks]
        deviation = np.std(chunked_reference_metric) * std_num
        mean_reference_metric = np.mean(chunked_reference_metric)
        lower_threshold = mean_reference_metric - deviation
        if lower_limit is not None:
            lower_threshold = np.maximum(lower_threshold, lower_limit)
        upper_threshold = mean_reference_metric + deviation
        if upper_limit is not None:
            upper_threshold = np.minimum(upper_threshold, upper_limit)
        return lower_threshold, upper_threshold

    def __eq__(self, other):
        """Establishes equality by comparing all properties."""
        return (
            self.components == other.components
            and self.upper_threshold == other.upper_threshold
            and self.lower_threshold == other.lower_threshold
        )

    def get_chunk_record(self, chunk_data: pd.DataFrame) -> Dict:
        """Returns a DataFrame containing the performance metrics for a given chunk."""
        if len(self.components) > 1:
            raise NotImplementedError(
                "cannot use default 'get_chunk_record' implementation when a metric has multiple components."
            )

        column_name = self.components[0][1]

        chunk_record = {}

        realized_value = self.calculate(chunk_data)
        sampling_error = self.sampling_error(chunk_data)

        chunk_record[f'{column_name}_sampling_error'] = sampling_error
        chunk_record[f'{column_name}'] = realized_value
        chunk_record[f'{column_name}_upper_threshold'] = self.upper_threshold
        chunk_record[f'{column_name}_lower_threshold'] = self.lower_threshold
        chunk_record[f'{column_name}_alert'] = (
            self.lower_threshold > realized_value if self.lower_threshold is not None else False
        ) or (self.upper_threshold < realized_value if self.upper_threshold is not None else False)

        return chunk_record

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def column_name(self) -> str:
        return self.components[0][1]

    @property
    def display_names(self) -> List[str]:
        return [c[0] for c in self.components]

    @property
    def column_names(self) -> List[str]:
        return [c[1] for c in self.components]


class MetricFactory:
    """A factory class that produces Metric instances based on a given magic string or a metric specification."""

    registry: Dict[str, Dict[ProblemType, Type[Metric]]] = {}

    @classmethod
    def _logger(cls) -> Logger:
        return logging.getLogger(__name__)

    @classmethod
    def create(cls, key: str, use_case: ProblemType, **kwargs) -> Metric:
        """Returns a Metric instance for a given key."""
        if not isinstance(key, str):
            raise InvalidArgumentsException(
                f"cannot create metric given a '{type(key)}'" "Please provide a string, function or Metric"
            )

        if key not in cls.registry:
            raise InvalidArgumentsException(
                f"unknown metric key '{key}' given. "
                "Should be one of ['roc_auc', 'f1', 'precision', 'recall', 'specificity', "
                "'accuracy', 'confusion_matrix', 'business_value']."
            )

        if use_case not in cls.registry[key]:
            raise RuntimeError(
                f"metric '{key}' is currently not supported for use case {use_case}. "
                "Please specify another metric or use one of these supported model types for this metric: "
                f"{[md.value for md in cls.registry[key]]}"
            )
        metric_class = cls.registry[key][use_case]
        return metric_class(**kwargs)

    @classmethod
    def register(cls, metric: str, use_case: ProblemType) -> Callable:
        def inner_wrapper(wrapped_class: Type[Metric]) -> Type[Metric]:
            if metric in cls.registry:
                if use_case in cls.registry[metric]:
                    cls._logger().warning(f"re-registering Metric for metric='{metric}' and use_case='{use_case}'")
                cls.registry[metric][use_case] = wrapped_class
            else:
                cls.registry[metric] = {use_case: wrapped_class}
            return wrapped_class

        return inner_wrapper


def _common_data_cleaning(y_true, y_pred):
    y_true, y_pred = (
        pd.Series(y_true).reset_index(drop=True),
        pd.Series(y_pred).reset_index(drop=True),
    )
    y_true = y_true[~y_pred.isna()]
    y_pred.dropna(inplace=True)

    y_pred = y_pred[~y_true.isna()]
    y_true.dropna(inplace=True)

    return y_true, y_pred
