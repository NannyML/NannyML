#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0
from __future__ import annotations

import typing
from enum import Enum
from typing import Dict, List, Optional, Union  # noqa: TYP001

if typing.TYPE_CHECKING:
    from typing_extensions import Protocol
else:
    Protocol = object

import pandas as pd

from nannyml.exceptions import InvalidArgumentsException
from nannyml.plots import Figure


class Result(Protocol):
    """The data that was calculated or estimated."""

    data: pd.DataFrame

    @property
    def empty(self) -> bool:
        ...

    @property
    def chunk_keys(self) -> pd.Series:
        ...

    @property
    def chunk_start_dates(self) -> pd.Series:
        ...

    @property
    def chunk_end_dates(self) -> pd.Series:
        ...

    @property
    def chunk_indices(self) -> pd.Series:
        ...

    @property
    def chunk_periods(self) -> pd.Series:
        ...

    @property
    def values(self) -> List[pd.Series]:
        ...

    def filter(
        self, period: str = 'analysis', metrics: Optional[Union[str, List[str]]] = None, *args, **kwargs
    ) -> Result:
        """"""

    def to_df(self, multilevel: bool = True) -> pd.DataFrame:
        """"""

    def plot(self, *args, **kwargs) -> Figure:
        ...


class Metric(Protocol):
    """Represents any kind of metric (or method) that can be calculated or estimated."""

    display_name: str
    column_name: str


class Calculator(Protocol):
    """Calculator base class."""

    def fit(self, reference_data: pd.DataFrame, *args, **kwargs) -> Calculator:
        """Fits the calculator on reference data."""

    def calculate(self, data: pd.DataFrame, *args, **kwargs) -> Result:
        """Perform a calculation based on analysis data."""


class Estimator(Protocol):
    """Estimator base class."""

    def fit(self, reference_data: pd.DataFrame, *args, **kwargs) -> Estimator:
        """Fits the estimator on reference data."""

    def estimate(self, data: pd.DataFrame, *args, **kwargs) -> Result:
        """Perform an estimation based on analysis data."""


ModelOutputsType = Union[str, Dict[str, str]]


def model_output_column_names(model_outputs: ModelOutputsType) -> List[str]:
    """Get model output column nanmes from inputs."""
    if model_outputs is None:
        return []
    if isinstance(model_outputs, str):
        return [model_outputs]
    elif isinstance(model_outputs, Dict):
        return [column_name for label, column_name in model_outputs.items()]
    else:
        raise InvalidArgumentsException(
            f"received object of type {type(model_outputs)}. ModelOutputsType should be "
            f"either a 'str' or a 'Dict[str, str]'"
        )


def class_labels(model_outputs: ModelOutputsType) -> List[str]:
    if isinstance(model_outputs, Dict):
        return sorted(list(model_outputs.keys()))
    else:
        raise InvalidArgumentsException(
            f"received object of type {type(model_outputs)}. Multiclass ModelOutputsType should be a 'Dict[str, str]'"
        )


class ProblemType(str, Enum):
    """Use cases NannyML supports."""

    CLASSIFICATION_BINARY = 'classification_binary'
    CLASSIFICATION_MULTICLASS = 'classification_multiclass'
    REGRESSION = 'regression'

    @staticmethod
    def parse(problem_type: str):
        if problem_type in 'classification_binary':
            return ProblemType.CLASSIFICATION_BINARY
        elif problem_type in 'classification_multiclass':
            return ProblemType.CLASSIFICATION_MULTICLASS
        elif problem_type in 'regression':
            return ProblemType.REGRESSION
        else:
            raise InvalidArgumentsException(
                f"unknown value for problem_type '{problem_type}'. Value should be one of "
                f"{[pt.value for pt in ProblemType]}"
            )
