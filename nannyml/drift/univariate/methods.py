#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0
from __future__ import annotations

import abc
import logging
from enum import Enum
from logging import Logger
from typing import Callable, Dict, Optional, Tuple
from copy import copy

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp
from scipy.spatial.distance import jensenshannon

from nannyml.exceptions import InvalidArgumentsException, NotFittedException
from nannyml.base import  _column_is_categorical

class Method(abc.ABC):
    """A performance metric used to calculate realized model performance."""

    def __init__(
        self,
        display_name: str,
        column_name: str,
        calculator,
        upper_threshold: float = None,
        lower_threshold: float = None,
        upper_threshold_limit: float = None,
        lower_threshold_limit: float = None,
    ):
        """Creates a new Metric instance.

        Parameters
        ----------
        display_name : str
            The name of the metric. Used to display in plots. If not given this name will be derived from the
            ``calculation_function``.
        column_name: str
            The name used to indicate the metric in columns of a DataFrame.
        calculator: PerformanceCalculator
            The calculator using the Metric instance.
        upper_threshold_limit : float, default=None
            An optional upper threshold for the performance metric.
        lower_threshold_limit : float, default=None
            An optional lower threshold for the performance metric.
        """
        self.display_name = display_name
        self.column_name = column_name

        from nannyml.drift.univariate import UnivariateDriftCalculator

        if not isinstance(calculator, UnivariateDriftCalculator):
            raise RuntimeError(
                f"{calculator.__class__.__name__} is not an instance " "of type " f"UnivariateDriftCalculator"
            )

        self.calculator: UnivariateDriftCalculator = calculator

        self.upper_threshold: Optional[float] = upper_threshold
        self.lower_threshold: Optional[float] = lower_threshold
        self.lower_threshold_limit: Optional[float] = lower_threshold_limit
        self.upper_threshold_limit: Optional[float] = upper_threshold_limit

    def fit(self, reference_data: pd.Series) -> Method:
        """Fits a Metric on reference data.

        Parameters
        ----------
        reference_data: pd.DataFrame
            The reference data used for fitting a Method. Must have target data available.

        """
        self._fit(reference_data)

        return self

    def _fit(self, reference_data: pd.Series) -> Method:
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Metric and it must implement the _fit method"
        )

    def calculate(self, data: pd.Series):
        """Calculates performance metrics on data.

        Parameters
        ----------
        data: pd.DataFrame
            The data to run the predefined methods on.
        """
        return self._calculate(data)

    def _calculate(self, data: pd.Series):
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Metric and it must implement the _calculate method"
        )

    # This is currenlty required because not all Methods use the same data to evaluate alerts.
    # E.g. KS and Chi2 alerts are still based on p-values, hence each method needs to individually decide how
    # to evaluate alert conditions...
    # To be refactored / removed when custom thresholding kicks in (and p-values are no longer used)
    def alert(self, data: pd.Series):
        """Evaluates if an alert has occurred for this method on the current chunk data.

        Parameters
        ----------
        data: pd.DataFrame
            The data to evaluate for an alert.
        """
        return self._alert(data)

    def _alert(self, data: pd.Series):
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Metric and it must implement the _alert method"
        )

    def __eq__(self, other):
        """Establishes equality by comparing all properties."""
        return (
            self.display_name == other.display_name
            and self.column_name == other.column_name
            and self.upper_threshold == other.upper_threshold
            and self.lower_threshold == other.lower_threshold
        )


class FeatureType(str, Enum):
    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"


class MethodFactory:
    """A factory class that produces Method instances given a 'key' string and a 'feature_type' it supports."""

    registry: Dict[str, Dict[FeatureType, Method]] = {}

    @classmethod
    def _logger(cls) -> Logger:
        return logging.getLogger(__name__)

    @classmethod
    def create(cls, key: str, feature_type: FeatureType, **kwargs) -> Method:
        """Returns a Metric instance for a given key."""
        if not isinstance(key, str):
            raise InvalidArgumentsException(f"cannot create method given a '{type(key)}'. Please provide a string.")

        if key not in cls.registry:
            raise InvalidArgumentsException(
                f"unknown method key '{key}' given. " "Should be one of ['jensen_shannon']."
            )

        if feature_type not in cls.registry[key]:
            raise InvalidArgumentsException(f"method {key} does not support {feature_type.value} features.")

        if kwargs is None:
            kwargs = {}

        method_class = cls.registry[key][feature_type]
        return method_class(**kwargs)  # type: ignore

    @classmethod
    def register(cls, key: str, feature_type: FeatureType) -> Callable:
        def inner_wrapper(wrapped_class: Method) -> Method:
            if key not in cls.registry:
                cls.registry[key] = {feature_type: wrapped_class}
            else:
                if feature_type not in cls.registry[key]:
                    cls.registry[key].update({feature_type: wrapped_class})
                else:
                    cls._logger().warning(f"re-registering Method for key='{key}' and feature_type='{feature_type}'")
                    cls.registry[key][feature_type] = wrapped_class

            return wrapped_class

        return inner_wrapper


@MethodFactory.register(key='jensen_shannon', feature_type=FeatureType.CONTINUOUS)
@MethodFactory.register(key='jensen_shannon', feature_type=FeatureType.CATEGORICAL)
class JensenShannonDistance(Method):
    """Calculates Jensen-Shannon distance."""

    def __init__(self, calculator):
        super().__init__(
            display_name='Jensen-Shannon distance',
            column_name='jensen_shannon',
            calculator=calculator,
            lower_threshold_limit=0,
        )
        self.upper_threshold = 0.1

        self._treat_as_type: Optional[str] = None
        self._bins: Optional[np.ndarray] = None
        self._reference_proba_in_bins: Optional[np.ndarray] = None

    def _fit(self, reference_data: pd.Series):
        if _column_is_categorical(reference_data):
            treat_as_type = 'cat'
        else:
            n_unique_values = len(np.unique(reference_data))
            len_reference = len(reference_data)
            if n_unique_values > 50 or n_unique_values/len_reference > 0.1:
                treat_as_type = 'cont'
            else:
                treat_as_type = 'cat'

        if treat_as_type == 'cont':
            bins = np.histogram_bin_edges(reference_data, bins='doane')
            reference_proba_in_bins = np.histogram(reference_data, bins=bins)[0] / len_reference
            self._bins = bins
            self._reference_proba_in_bins = reference_proba_in_bins
        else:
            reference_unique, reference_counts = np.unique(reference_data, return_counts=True)
            reference_proba_per_unique = reference_counts/len(reference_data)
            self._bins = reference_unique
            self._reference_proba_in_bins = reference_proba_per_unique


        self._treat_as_type = treat_as_type

        return self

    def _calculate(self, data: pd.Series):
        reference_proba_in_bins = copy(self._reference_proba_in_bins)
        if self._treat_as_type == 'cont':
            len_data = len(data)
            data_proba_in_bins = np.histogram(data, bins=self._bins)[0] / len_data

        else:
            data_unique, data_counts = np.unique(data, return_counts=True)
            data_counts_dic = dict(zip(data_unique, data_counts))
            data_count_on_ref_bins = [
                data_counts_dic[key] if key in data_counts_dic else 0
                for key in self._bins]
            data_proba_in_bins = np.array(data_count_on_ref_bins) / len(data)

        leftover = 1 - np.sum(data_proba_in_bins)
        if leftover > 0:
            data_proba_in_bins = np.append(data_proba_in_bins, leftover)
            reference_proba_in_bins = np.append(reference_proba_in_bins, 0)

        distance = jensenshannon(reference_proba_in_bins, data_proba_in_bins)
        self._p_value = None

        del reference_proba_in_bins

        return distance


    def _alert(self, data: pd.Series):
        value = self.calculate(data)
        return (self.lower_threshold is not None and value < self.lower_threshold) or (
            self.upper_threshold is not None and value > self.upper_threshold
        )


@MethodFactory.register(key='kolmogorov_smirnov', feature_type=FeatureType.CONTINUOUS)
class KolmogorovSmirnovStatistic(Method):
    def __init__(self, calculator):
        super().__init__(
            display_name='Kolmogorov-Smirnov statistic',
            column_name='kolmogorov_smirnov',
            calculator=calculator,
            upper_threshold_limit=1,
            lower_threshold=0.05,
        )
        self._reference_data: Optional[pd.Series] = None
        self._p_value: Optional[float] = None

    def _fit(self, reference_data: pd.Series) -> Method:
        self._reference_data = reference_data
        return self

    def _calculate(self, data: pd.Series):
        if self._reference_data is None:
            raise NotFittedException(
                "tried to call 'calculate' on an unfitted method " f"{self.display_name}. Please run 'fit' first"
            )

        stat, p_value = ks_2samp(self._reference_data, data)
        self._p_value = p_value
        return stat

    def _alert(self, data: pd.Series):
        if self._p_value is None:
            _, self._p_value = ks_2samp(self._reference_data, data)

        alert = self._p_value < self.lower_threshold
        self._p_value = None  # just cleaning up state before running on new chunk data (optimization)

        return alert


@MethodFactory.register(key='chi2', feature_type=FeatureType.CATEGORICAL)
class Chi2Statistic(Method):
    def __init__(self, calculator):
        super().__init__(
            display_name='Chi2',
            column_name='chi2',
            calculator=calculator,
            upper_threshold_limit=1.0,
            lower_threshold=0.05,
        )
        self._reference_data: Optional[pd.Series] = None
        self._p_value: Optional[float] = None

    def _fit(self, reference_data: pd.Series) -> Method:
        self._reference_data = reference_data
        return self

    def _calculate(self, data: pd.Series):
        if self._reference_data is None:
            raise NotFittedException(
                "tried to call 'calculate' on an unfitted method " f"{self.display_name}. Please run 'fit' first"
            )

        stat, p_value, _, _ = chi2_contingency(
            pd.concat(
                [self._reference_data.value_counts(), data.value_counts()],  # type: ignore
                axis=1,
            ).fillna(0)
        )
        self._p_value = p_value
        return stat

    def _alert(self, data: pd.Series):
        if self._p_value is None:
            _, self._p_value, _, _ = chi2_contingency(
                pd.concat(
                    [self._reference_data.value_counts(), data.value_counts()],  # type: ignore
                    axis=1,
                ).fillna(0)
            )

        alert = self._p_value < self.lower_threshold
        self._p_value = None
        return alert
