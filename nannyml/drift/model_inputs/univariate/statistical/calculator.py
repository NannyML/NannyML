#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Statistical drift calculation using `Kolmogorov-Smirnov` and `chi2-contingency` tests."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, ks_2samp

from nannyml.base import AbstractCalculator
from nannyml.chunk import Chunker
from nannyml.drift.model_inputs.univariate.statistical.results import UnivariateStatisticalDriftCalculatorResult
from nannyml.metadata.base import NML_METADATA_PERIOD_COLUMN_NAME

ALERT_THRESHOLD_P_VALUE = 0.05


class UnivariateStatisticalDriftCalculator(AbstractCalculator):
    """A drift calculator that relies on statistics to detect drift."""

    def __init__(
        self,
        feature_column_names: List[str],
        timestamp_column_name: str,
        chunk_size: int = None,
        chunk_number: int = None,
        chunk_period: str = None,
        chunker: Chunker = None,
    ):
        """Constructs a new UnivariateStatisticalDriftCalculator.

        Parameters
        ----------
        feature_column_names: List[str]
            A list containing the names of features in the provided data set.
            A drift score will be calculated for each entry in this list.
        chunk_size: int
            Splits the data into chunks containing `chunks_size` observations.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunk_number: int
            Splits the data into `chunk_number` pieces.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunk_period: str
            Splits the data according to the given period.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunker : Chunker
            The `Chunker` used to split the data sets into a lists of chunks.

        Examples
        --------
        >>> import nannyml as nml
        >>> ref_df, ana_df, _ = nml.load_synthetic_binary_classification_dataset()
        >>> metadata = nml.extract_metadata(ref_df)
        >>> # Create a calculator that will chunk by week
        >>> drift_calc = nml.UnivariateStatisticalDriftCalculator(model_metadata=metadata, chunk_period='W')
        """
        super(UnivariateStatisticalDriftCalculator, self).__init__(chunk_size, chunk_number, chunk_period, chunker)

        self.feature_column_names = feature_column_names
        self.continuous_column_names: List[str] = []
        self.categorical_column_names: List[str] = []

        self.timestamp_column_name = timestamp_column_name

        self._reference_data = None

    def _fit(self, reference_data: pd.DataFrame, *args, **kwargs) -> UnivariateStatisticalDriftCalculator:
        """Fits the drift calculator using a set of reference data.

        Parameters
        ----------
        reference_data : pd.DataFrame
            A reference data set containing predictions (labels and/or probabilities) and target values.

        Returns
        -------
        calculator: DriftCalculator
            The fitted calculator.

        Examples
        --------
        >>> import nannyml as nml
        >>> ref_df, ana_df, _ = nml.load_synthetic_binary_classification_dataset()
        >>> metadata = nml.extract_metadata(ref_df, model_type=nml.ModelType.CLASSIFICATION_BINARY)
        >>> # Create a calculator and fit it
        >>> drift_calc = nml.UnivariateStatisticalDriftCalculator(model_metadata=metadata, chunk_period='W').fit(ref_df)

        """
        # check metadata for required properties
        # self.model_metadata.check_has_fields(['period_column_name', 'timestamp_column_name', 'features'])

        # reference_data = preprocess(data=reference_data, metadata=self.model_metadata, reference=True)

        # store state
        self._reference_data = reference_data.copy(deep=True)
        self._reference_data[NML_METADATA_PERIOD_COLUMN_NAME] = 'reference'  # type: ignore

        return self

    def _calculate(self, data: pd.DataFrame, *args, **kwargs) -> UnivariateStatisticalDriftCalculatorResult:
        """Calculates the data reconstruction drift for a given data set.

        Parameters
        ----------
        data : pd.DataFrame
            The dataset to calculate the reconstruction drift for.

        Returns
        -------
        reconstruction_drift: UnivariateStatisticalDriftCalculatorResult
            A :class:`result<nannyml.drift.model_inputs.univariate.statistical.results.UnivariateDriftResult>`
            object where each row represents a :class:`~nannyml.chunk.Chunk`,
            containing :class:`~nannyml.chunk.Chunk` properties and the reconstruction_drift calculated
            for that :class:`~nannyml.chunk.Chunk`.

        Examples
        --------
        >>> import nannyml as nml
        >>> ref_df, ana_df, _ = nml.load_synthetic_binary_classification_dataset()
        >>> metadata = nml.extract_metadata(ref_df, model_type=nml.ModelType.CLASSIFICATION_BINARY)
        >>> # Create a calculator and fit it
        >>> drift_calc = nml.UnivariateStatisticalDriftCalculator(model_metadata=metadata, chunk_period='W').fit(ref_df)
        >>> drift = drift_calc.calculate(data)
        """
        # Check metadata for required properties
        # self.model_metadata.check_has_fields(['period_column_name', 'timestamp_column_name', 'features'])

        # data = preprocess(data=data, metadata=self.model_metadata)
        data[NML_METADATA_PERIOD_COLUMN_NAME] = 'analysis'

        # Get lists of categorical <-> categorical features
        self.continuous_column_names = [
            col for col in data[self.feature_column_names].select_dtypes(include=['float64', 'int64']).columns
        ]
        self.categorical_column_names = [
            col
            for col in data[self.feature_column_names]
            .select_dtypes(include=['object', 'string', 'category', 'bool'])
            .columns
        ]

        # features_and_metadata = NML_METADATA_COLUMNS + self.selected_features
        chunks = self.chunker.split(
            data,
            self.timestamp_column_name,
            columns=self.feature_column_names + [NML_METADATA_PERIOD_COLUMN_NAME],
            minimum_chunk_size=500,
        )

        chunk_drifts = []
        # Calculate chunk-wise drift statistics.
        # Append all into resulting DataFrame indexed by chunk key.
        for chunk in chunks:
            chunk_drift: Dict[str, Any] = {
                'key': chunk.key,
                'start_index': chunk.start_index,
                'end_index': chunk.end_index,
                'start_date': chunk.start_datetime,
                'end_date': chunk.end_datetime,
                'period': 'analysis' if chunk.is_transition else chunk.period,
            }

            for column in self.categorical_column_names:
                statistic, p_value, _, _ = chi2_contingency(
                    pd.concat(
                        [
                            self._reference_data[column].value_counts(),  # type: ignore
                            chunk.data[column].value_counts(),
                        ],
                        axis=1,
                    ).fillna(0)
                )
                chunk_drift[f'{column}_chi2'] = statistic
                chunk_drift[f'{column}_p_value'] = np.round(p_value, decimals=3)
                chunk_drift[f'{column}_alert'] = (p_value < ALERT_THRESHOLD_P_VALUE) and (
                    chunk.data[NML_METADATA_PERIOD_COLUMN_NAME] == 'analysis'
                ).all()
                chunk_drift[f'{column}_threshold'] = ALERT_THRESHOLD_P_VALUE

            for column in self.continuous_column_names:
                statistic, p_value = ks_2samp(self._reference_data[column], chunk.data[column])  # type: ignore
                chunk_drift[f'{column}_dstat'] = statistic
                chunk_drift[f'{column}_p_value'] = np.round(p_value, decimals=3)
                chunk_drift[f'{column}_alert'] = (p_value < ALERT_THRESHOLD_P_VALUE) and (
                    chunk.data[NML_METADATA_PERIOD_COLUMN_NAME] == 'analysis'
                ).all()
                chunk_drift[f'{column}_threshold'] = ALERT_THRESHOLD_P_VALUE

            chunk_drifts.append(chunk_drift)

        res = pd.DataFrame.from_records(chunk_drifts)
        res = res.reset_index(drop=True)
        res.attrs['nml_drift_calculator'] = __name__

        self.result = res

        from nannyml.drift.model_inputs.univariate.statistical.results import UnivariateStatisticalDriftCalculatorResult

        return UnivariateStatisticalDriftCalculatorResult(results_data=res, calculator=self)
        # return self.result
