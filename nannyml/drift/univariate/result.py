#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Contains the results of the univariate statistical drift calculation and provides plotting functionality."""
import copy
from typing import List, Optional, Union

import pandas as pd
import plotly.graph_objects as go

from nannyml.base import AbstractCalculatorResult, _column_is_continuous
from nannyml.chunk import Chunk
from nannyml.drift.univariate.methods import Method, MethodFactory
from nannyml.exceptions import InvalidArgumentsException
from nannyml.plots._joy_plot import _joy_plot
from nannyml.plots._stacked_bar_plot import _stacked_bar_plot
from nannyml.plots._step_plot import _step_plot


class Result(AbstractCalculatorResult):
    """Contains the results of the univariate statistical drift calculation and provides plotting functionality."""

    def __init__(self, results_data: pd.DataFrame, calculator):
        super().__init__(results_data)

        from nannyml.drift.univariate.calculator import UnivariateDriftCalculator

        if not isinstance(calculator, UnivariateDriftCalculator):
            raise RuntimeError(
                f"{calculator.__class__.__name__} is not an instance of type " f"UnivariateDriftCalculator"
            )
        self.calculator = calculator

    def _filter(self, period: str, *args, **kwargs) -> AbstractCalculatorResult:
        if 'column_names' in kwargs:
            column_names = kwargs['column_names']
        else:
            column_names = self.calculator.column_names

        if 'methods' in kwargs:
            methods = kwargs['methods']
        else:
            methods = list(set(self.calculator.categorical_method_names + self.calculator.continuous_method_names))

        data = pd.concat([self.data.loc[:, (['chunk'])], self.data.loc[:, (column_names, methods)]], axis=1)

        if period != 'all':
            data = data.loc[data[('chunk', 'chunk', 'period')] == period, :]

        data = data.reset_index(drop=True)

        return Result(results_data=data, calculator=copy.deepcopy(self.calculator))

    def plot(
        self,
        kind: str = 'feature_drift',
        method: Union[str, Method] = 'jensen_shannon',
        column_name: str = None,
        plot_reference: bool = False,
        *args,
        **kwargs,
    ) -> Optional[go.Figure]:
        """Renders plots for metrics returned by the univariate distance drift calculator.

        For any feature you can render the statistic value or p-values as a step plot, or create a distribution plot.
        Select a plot using the ``kind`` parameter:

        - ``feature_drift``
                plots drift per :class:`~nannyml.chunk.Chunk` for a single feature of a chunked data set.
        - ``feature_distribution``
                plots feature distribution per :class:`~nannyml.chunk.Chunk`.
                Joyplot for continuous features, stacked bar charts for categorical features.

        Parameters
        ----------
        kind: str, default=`feature_drift`
            The kind of plot you want to have. Allowed values are `feature_drift`` and ``feature_distribution``.
        column_name : str
            Column name identifying a feature according to the preset model metadata. The function will raise an
            exception when no feature using that column name was found in the metadata.
            Either ``feature_column_name`` or ``feature_label`` should be specified.
        method: str
            The name of the metric to plot. Allowed values are [`jensen_shannon`].
        plot_reference: bool, default=False
            Indicates whether to include the reference period in the plot or not. Defaults to ``False``.

        Returns
        -------
        fig: :class:`plotly.graph_objs._figure.Figure`
            A :class:`~plotly.graph_objs._figure.Figure` object containing the requested drift plot.

            Can be saved to disk using the :meth:`~plotly.graph_objs._figure.Figure.write_image` method
            or shown rendered on screen using the :meth:`~plotly.graph_objs._figure.Figure.show` method.

        Examples
        --------
        >>> import nannyml as nml
        >>> reference, analysis, _ = nml.load_synthetic_car_price_dataset()
        >>> calc = nml.DistanceDriftCalculator(
        ...     timestamp_column_name='timestamp',
        ...     metrics=['jensen_shannon'],
        ...     column_names=[col for col in reference.columns if col not in ['timestamp', 'y_pred', 'y_true']]
        ... ).fit(reference)
        >>> res = calc.calculate(analysis)
        >>> for feature in calc.column_names:
        ...     for metric in calc.metrics:
        ...         res.plot(kind='feature_distribution', feature_column_name=feature, metric=metric).show()

        """
        if method is None:
            raise InvalidArgumentsException(
                "no value for 'method' given. Please provide the name of a metric to display."
            )
        if kind == 'feature_drift':
            if column_name is None:
                raise InvalidArgumentsException("must specify a feature to plot " "using the 'column_name' parameter")
            return self.plot_feature_drift(method, column_name, plot_reference)
        elif kind == 'feature_distribution':
            if column_name is None:
                raise InvalidArgumentsException("must specify a feature to plot " "using the 'column_name' parameter")
            return self._plot_feature_distribution(
                analysis_data=self.calculator.previous_analysis_data,
                plot_reference=plot_reference,
                drift_data=self.to_df(multilevel=False),
                column_name=column_name,
                method=method,
            )
        else:
            raise InvalidArgumentsException(
                f"unknown plot kind '{kind}'. " f"Please provide on of: ['feature_drift', 'feature_distribution']."
            )

    def _plot_feature_distribution(
        self,
        analysis_data: pd.DataFrame,
        drift_data: pd.DataFrame,
        column_name: str,
        method: Union[str, Method],
        plot_reference: bool,
    ) -> go.Figure:
        """Plots the data distribution and associated drift for each chunk of a given continuous feature."""
        if _column_is_continuous(analysis_data[column_name]):
            return self._plot_continuous_feature_distribution(
                analysis_data, drift_data, column_name, method, plot_reference
            )
        else:
            return self._plot_categorical_feature_distribution(
                analysis_data, drift_data, column_name, method, plot_reference
            )
        # pass

    def plot_feature_drift(
        self,
        method: Union[str, Method],
        column_name: str,
        plot_reference: bool = False,
    ) -> go.Figure:
        """Renders a line plot for a chosen metric of univariate statistical feature drift calculation results."""
        result_data = self.to_df(multilevel=False)

        if isinstance(method, str):
            _supported_feature_types = list(MethodFactory.registry[method].keys())
            if len(_supported_feature_types) == 0:
                raise InvalidArgumentsException(f"method '{method}' can not be used for column '{column_name}'")
            method = MethodFactory.create(
                key=method, feature_type=_supported_feature_types[0], calculator=self.calculator
            )

        if not plot_reference:
            result_data = result_data[result_data['chunk_chunk_period'] == 'analysis']

        is_time_based_x_axis = self.calculator.timestamp_column_name is not None

        fig = _step_plot(
            table=result_data,
            metric_column_name=f'{column_name}_{method.column_name}_value',
            chunk_column_name='chunk_chunk_key',
            chunk_index_column_name='chunk_chunk_chunk_index',
            chunk_type_column_name='chunk_chunk_period',
            start_date_column_name='chunk_chunk_start_date' if is_time_based_x_axis else None,
            end_date_column_name='chunk_chunk_end_date' if is_time_based_x_axis else None,
            drift_column_name=f'{column_name}_{method.column_name}_alert',
            lower_threshold_column_name=f'{column_name}_{method.column_name}_lower_threshold',
            upper_threshold_column_name=f'{column_name}_{method.column_name}_upper_threshold',
            hover_labels=['Chunk', f'{method.display_name}', 'Target data'],
            title=f'{method.display_name} distance for {column_name}',
            y_axis_title=f'{method.display_name}',
            v_line_separating_analysis_period=plot_reference,
        )
        return fig

    def _plot_continuous_feature_distribution(
        self,
        data: pd.DataFrame,
        drift_data: pd.DataFrame,
        column_name: str,
        method: Union[str, Method],
        plot_reference: bool,
    ) -> go.Figure:
        """Plots the data distribution and associated drift for each chunk of a given continuous feature."""
        if isinstance(method, str):
            _supported_feature_types = list(MethodFactory.registry[method].keys())
            if len(_supported_feature_types) == 0:
                raise InvalidArgumentsException(f"method '{method}' can not be used for column '{column_name}'")
            method = MethodFactory.create(
                key=method, feature_type=_supported_feature_types[0], calculator=self.calculator
            )

        if not plot_reference:
            drift_data = drift_data.loc[drift_data['chunk_chunk_period'] == 'analysis']

        x_axis_title = f'{column_name}'
        drift_column_name = f'{column_name}_{method.column_name}_alert'
        title = f'Distribution over time for {column_name}'
        key_column_name = 'chunk_chunk_key'

        data['period'] = 'analysis'
        feature_table = _create_feature_table(self.calculator.chunker.split(data), key_column_name)

        if plot_reference:
            reference_feature_table = _create_feature_table(
                self.calculator.chunker.split(self.calculator.previous_reference_data), key_column_name
            )
            reference_feature_table['chunk_chunk_period'] = 'reference'
            feature_table = pd.concat([reference_feature_table, feature_table], ignore_index=True)

        is_time_based_x_axis = self.calculator.timestamp_column_name is not None

        fig = _joy_plot(
            feature_table=feature_table,
            drift_table=drift_data,
            chunk_column_name='chunk_chunk_key',
            chunk_index_column_name='chunk_chunk_chunk_index',
            chunk_type_column_name='chunk_chunk_period',
            drift_column_name=drift_column_name,
            feature_column_name=column_name,
            x_axis_title=x_axis_title,
            title=title,
            style='vertical',
            start_date_column_name='chunk_chunk_start_date' if is_time_based_x_axis else None,
            end_date_column_name='chunk_chunk_end_date' if is_time_based_x_axis else None,
        )
        return fig

    def _plot_categorical_feature_distribution(
        self,
        data: pd.DataFrame,
        drift_data: pd.DataFrame,
        column_name: str,
        method: Union[str, Method],
        plot_reference: bool,
    ) -> go.Figure:
        """Plots the data distribution and associated drift for each chunk of a given categorical feature."""
        if isinstance(method, str):
            _supported_feature_types = list(MethodFactory.registry[method].keys())
            if len(_supported_feature_types) == 0:
                raise InvalidArgumentsException(f"method '{method}' can not be used for column '{column_name}'")
            method = MethodFactory.create(
                key=method, feature_type=_supported_feature_types[0], calculator=self.calculator
            )

        if not plot_reference:
            drift_data = drift_data.loc[drift_data['chunk_chunk_period'] == 'analysis']

        yaxis_title = f'{column_name}'
        drift_column_name = f'{column_name}_{method.column_name}_alert'
        title = f'Distribution over time for {column_name}'
        key_column_name = 'chunk_chunk_key'

        data['chunk_chunk_period'] = 'analysis'
        feature_table = _create_feature_table(self.calculator.chunker.split(data), key_column_name)

        if plot_reference:
            reference_feature_table = _create_feature_table(
                self.calculator.chunker.split(self.calculator.previous_reference_data), key_column_name
            )
            reference_feature_table['chunk_chunk_period'] = 'reference'
            feature_table = pd.concat([reference_feature_table, feature_table], ignore_index=True)

        is_time_based_x_axis = self.calculator.timestamp_column_name is not None

        fig = _stacked_bar_plot(
            feature_table=feature_table,
            drift_table=drift_data,
            chunk_column_name='chunk_chunk_key',
            chunk_type_column_name='chunk_chunk_period',
            chunk_index_column_name='chunk_chunk_chunk_index',
            drift_column_name=drift_column_name,
            feature_column_name=column_name,
            yaxis_title=yaxis_title,
            title=title,
            start_date_column_name='chunk_chunk_start_date' if is_time_based_x_axis else None,
            end_date_column_name='chunk_chunk_end_date' if is_time_based_x_axis else None,
        )
        return fig


def _create_feature_table(chunks: List[Chunk], key_column_name: str) -> pd.DataFrame:
    return pd.concat([chunk.data.assign(**{key_column_name: chunk.key}) for chunk in chunks])
