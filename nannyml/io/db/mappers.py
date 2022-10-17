#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0
import abc
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List

from nannyml._typing import ProblemType
from nannyml.drift.model_inputs.multivariate.data_reconstruction.results import Result as DataReconstructionDriftResult
from nannyml.drift.model_inputs.univariate.statistical.results import Result as StatisticalFeatureDriftResult
from nannyml.drift.model_outputs.univariate.statistical.results import Result as StatisticalOutputDriftResult
from nannyml.drift.target.target_distribution.result import Result as TargetDriftResult
from nannyml.exceptions import InvalidArgumentsException
from nannyml.io.db.entities import CBPEPerformanceMetric, DataReconstructionFeatureDriftMetric, DLEPerformanceMetric
from nannyml.io.db.entities import Metric as DbMetric
from nannyml.io.db.entities import (
    RealizedPerformanceMetric,
    StatisticalFeatureDriftMetric,
    StatisticalOutputDriftMetric,
    TargetDriftMetric,
)
from nannyml.performance_calculation.result import Result as RealizedPerformanceResult
from nannyml.performance_estimation.confidence_based.results import Result as CBPEResult
from nannyml.performance_estimation.direct_loss_estimation.result import Result as DLEResult


class Mapper(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        """Maps a result to a list of Metric entities."""


def _fully_qualified_class_name(result):
    return f"{result.__module__}.{result.__name__}"


class MapperFactory:
    """A factory class that produces Mapper instances for a given Result subclass."""

    registry: Dict[str, Mapper] = {}

    @classmethod
    def _logger(cls) -> logging.Logger:
        return logging.getLogger(__name__)

    @classmethod
    def create(cls, result, kwargs: Dict[str, Any] = None) -> Mapper:
        """Returns a Mapper instance for a given result class."""

        if kwargs is None:
            kwargs = {}

        key = _fully_qualified_class_name(result.__class__)

        if key not in cls.registry:
            raise InvalidArgumentsException(
                f"unknown result class '{key}' given. "
                f"Currently registered result classes are: {list(cls.registry.keys())}"
            )

        mapper_class = cls.registry[key]
        return mapper_class(**kwargs)  # type: ignore

    @classmethod
    def register(cls, result) -> Callable:
        key = _fully_qualified_class_name(result)

        def inner_wrapper(wrapped_class: Mapper) -> Mapper:
            if key in cls.registry:
                cls._logger().warning(f"re-registering Metric for result_class='{key}'")
            cls.registry[key] = wrapped_class
            return wrapped_class

        return inner_wrapper


@MapperFactory.register(StatisticalFeatureDriftResult)
class StatisticalFeatureDriftResultMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(
            feature_name: str, metric_name: str, start_date: datetime, end_date: datetime, value, alert: bool
        ) -> DbMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return StatisticalFeatureDriftMetric(
                feature_name=feature_name,
                metric_name=metric_name,
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                alert=alert,
                **metric_args,
            )

        if not isinstance(result, StatisticalFeatureDriftResult):
            raise InvalidArgumentsException(f"{self.__class__.__name__} can not deal with '{type(result)}'")

        if result.calculator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[StatisticalFeatureDriftMetric] = []

        for feature_metric_col in [
            col for col in result.data.columns if str(col).endswith(tuple(result.col_suffix_to_metric))
        ]:
            idx = feature_metric_col.rindex('_')
            feature_name = feature_metric_col[0:idx]
            metric_name = result.col_suffix_to_metric[feature_metric_col[idx:]]
            alert_col = f'{feature_name}_alert'

            res += (
                result.data.loc[
                    result.data['period'] == 'analysis', ['start_date', 'end_date', feature_metric_col, alert_col]
                ]
                .apply(lambda r: _parse(feature_name, metric_name, *r), axis=1)
                .to_list()
            )

        return res


@MapperFactory.register(DataReconstructionDriftResult)
class ReconstructionErrorDriftResultMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(
            column_name: str,
            start_date: datetime,
            end_date: datetime,
            value,
            upper_threshold,
            lower_threshold,
            alert,
        ) -> DbMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return DataReconstructionFeatureDriftMetric(
                metric_name=result.col_to_metric_label[column_name],
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                upper_threshold=upper_threshold,
                lower_threshold=lower_threshold,
                alert=alert,
                **metric_args,
            )

        if not isinstance(result, DataReconstructionDriftResult):
            raise InvalidArgumentsException(f"{self.__class__.__name__} can not deal with '{type(result)}'")

        if result.calculator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[DbMetric] = []

        for metric_col in result.col_to_metric_label.keys():
            res += (
                result.data.loc[
                    result.data['period'] == 'analysis',
                    ['start_date', 'end_date', metric_col, 'upper_threshold', 'lower_threshold', 'alert'],
                ]
                .apply(lambda r: _parse(metric_col, *r), axis=1)
                .to_list()
            )

        return res


@MapperFactory.register(StatisticalOutputDriftResult)
class StatisticalOutputDriftMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(
            output_name: str, metric_name: str, start_date: datetime, end_date: datetime, value, alert: bool
        ) -> StatisticalOutputDriftMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return StatisticalOutputDriftMetric(
                output_name=output_name,
                metric_name=metric_name,
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                alert=alert,
                **metric_args,
            )

        if result.calculator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[StatisticalOutputDriftMetric] = []

        for output_metric_col in [
            col for col in result.data.columns if str(col).endswith(tuple(result.col_suffix_to_metric))
        ]:
            idx = output_metric_col.rindex('_')
            output = output_metric_col[0:idx]
            metric = result.col_suffix_to_metric[output_metric_col[idx:]]
            alert_col = f'{output}_alert'

            res += (
                result.data.loc[
                    result.data['period'] == 'analysis', ['start_date', 'end_date', output_metric_col, alert_col]
                ]
                .apply(lambda r: _parse(output, metric, *r), axis=1)
                .to_list()
            )

        return res


@MapperFactory.register(TargetDriftResult)
class TargetDriftMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(target_name: str, start_date: datetime, end_date: datetime, value, alert: bool) -> TargetDriftMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return TargetDriftMetric(
                target_name=target_name,
                metric_name="KS" if result.calculator.problem_type == ProblemType.REGRESSION else "Chi2",
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                alert=alert,
                **metric_args,
            )

        if result.calculator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[TargetDriftMetric] = []

        res += (
            result.data.loc[
                result.data['period'] == 'analysis', ['start_date', 'end_date', 'statistical_target_drift', 'alert']
            ]
            .apply(lambda r: _parse(result.calculator.y_true, *r), axis=1)
            .to_list()
        )

        return res


@MapperFactory.register(RealizedPerformanceResult)
class RealizedPerformanceMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(
            metric_name: str,
            start_date: datetime,
            end_date: datetime,
            value,
            upper_threshold,
            lower_threshold,
            alert: bool,
        ) -> RealizedPerformanceMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return RealizedPerformanceMetric(
                metric_name=metric_name,
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                upper_threshold=upper_threshold,
                lower_threshold=lower_threshold,
                alert=alert,
                **metric_args,
            )

        if result.calculator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[RealizedPerformanceMetric] = []

        for metric in result.calculator.metrics:
            lower_threshold_col = f'{metric.column_name}_lower_threshold'
            upper_threshold_col = f'{metric.column_name}_upper_threshold'
            alert_col = f'{metric.column_name}_alert'

            res += (
                result.data.loc[
                    result.data['period'] == 'analysis',
                    ['start_date', 'end_date', metric.column_name, upper_threshold_col, lower_threshold_col, alert_col],
                ]
                .apply(lambda r: _parse(metric.display_name, *r), axis=1)
                .to_list()
            )

        return res


@MapperFactory.register(CBPEResult)
class CBPEMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(
            metric_name: str,
            start_date: datetime,
            end_date: datetime,
            value,
            upper_threshold,
            lower_threshold,
            alert: bool,
        ) -> CBPEPerformanceMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return CBPEPerformanceMetric(
                metric_name=metric_name,
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                upper_threshold=upper_threshold,
                lower_threshold=lower_threshold,
                alert=alert,
                **metric_args,
            )

        if result.estimator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[CBPEPerformanceMetric] = []

        for metric in result.estimator.metrics:
            metric_col = f'estimated_{metric.column_name}'
            lower_threshold_col = f'lower_threshold_{metric.column_name}'
            upper_threshold_col = f'upper_threshold_{metric.column_name}'
            alert_col = f'alert_{metric.column_name}'

            res += (
                result.data.loc[
                    result.data['period'] == 'analysis',
                    ['start_date', 'end_date', metric_col, upper_threshold_col, lower_threshold_col, alert_col],
                ]
                .apply(lambda r: _parse(metric.display_name, *r), axis=1)
                .to_list()
            )

        return res


@MapperFactory.register(DLEResult)
class DLEMapper(Mapper):
    def map_to_entity(self, result, **metric_args) -> List[DbMetric]:
        def _parse(
            metric_name: str,
            start_date: datetime,
            end_date: datetime,
            value,
            upper_threshold,
            lower_threshold,
            alert: bool,
        ) -> DLEPerformanceMetric:
            timestamp = start_date + (end_date - start_date) / 2

            return DLEPerformanceMetric(
                metric_name=metric_name,
                start_timestamp=start_date,
                end_timestamp=end_date,
                timestamp=timestamp,
                value=value,
                upper_threshold=upper_threshold,
                lower_threshold=lower_threshold,
                alert=alert,
                **metric_args,
            )

        if result.estimator.timestamp_column_name is None:
            raise NotImplementedError(
                'no timestamp column was specified. Listing metrics currently requires a '
                'timestamp column to be specified and present'
            )

        res: List[DLEPerformanceMetric] = []

        for metric in result.estimator.metrics:
            metric_col = f'estimated_{metric.column_name}'
            lower_threshold_col = f'lower_threshold_{metric.column_name}'
            upper_threshold_col = f'upper_threshold_{metric.column_name}'
            alert_col = f'alert_{metric.column_name}'

            res += (
                result.data.loc[
                    result.data['period'] == 'analysis',
                    ['start_date', 'end_date', metric_col, upper_threshold_col, lower_threshold_col, alert_col],
                ]
                .apply(lambda r: _parse(metric.display_name, *r), axis=1)
                .to_list()
            )

        return res
