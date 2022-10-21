#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""NannyML drift calculation module.

This module currently contains the following implementations of drift calculation:

- Statistical drift calculation: Calculating drift using Kolmogorov-Smirnov test for continuous features
  and Chi-squared test for categorical features.
- Reconstruction error drift calculation: Detect drift by performing dimensionality reduction on the model
  inputs and then applying the inverse transofrmation on the latent (reduced) space.

"""
from .model_inputs.univariate.distance import DistanceDriftCalculator
from .model_inputs.univariate.statistical import UnivariateStatisticalDriftCalculator
from .model_outputs.univariate.statistical import StatisticalOutputDriftCalculator
from .multivariate.data_reconstruction import DataReconstructionDriftCalculator
from .ranking import AlertCountRanking, Ranker, Ranking
from .target.target_distribution import TargetDistributionCalculator
from .univariate import FeatureType, Method, MethodFactory, UnivariateDriftCalculator
