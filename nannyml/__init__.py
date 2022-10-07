# Author:   Niels Nuyttens  <niels@nannyml.com>
#
# License: Apache Software License 2.0

# TODO wording

"""The NannyML library, helping you maintain model performance since 2020.

Use the library to:
- Calculate drift on model inputs, outputs and ground truth
- Calculate performance metrics for your model
- Estimate model performance metrics in the absence of ground truth
"""

__author__ = """Niels Nuyttens"""
__email__ = 'niels@nannyml.com'


# PEP0440 compatible formatted version, see:
# https://www.python.org/dev/peps/pep-0440/
#
# Generic release markers:
#   X.Y.0   # For first release after an increment in Y
#   X.Y.Z   # For bugfix releases
#
# Admissible pre-release markers:
#   X.Y.ZaN   # Alpha release
#   X.Y.ZbN   # Beta release
#   X.Y.ZrcN  # Release Candidate
#   X.Y.Z     # Final release
#
# Dev branch marker is: 'X.Y.dev' or 'X.Y.devN' where N is an integer.
# 'X.Y.dev0' is the canonical version of 'X.Y.dev'
#
__version__ = '0.6.3'

import logging

from .calibration import Calibrator, IsotonicCalibrator, needs_calibration
from .chunk import Chunk, Chunker, CountBasedChunker, DefaultChunker, PeriodBasedChunker, SizeBasedChunker
from .cli import cli, run
from .datasets import (
    load_modified_california_housing_dataset,
    load_synthetic_binary_classification_dataset,
    load_synthetic_car_loan_dataset,
    load_synthetic_car_price_dataset,
    load_synthetic_multiclass_classification_dataset,
)
from .drift import (
    AlertCountRanking,
    DataReconstructionDriftCalculator,
    DistanceDriftCalculator,
    Ranker,
    Ranking,
    StatisticalOutputDriftCalculator,
    TargetDistributionCalculator,
    UnivariateStatisticalDriftCalculator,
)
from .exceptions import ChunkerException, InvalidArgumentsException, MissingMetadataException
from .performance_calculation import PerformanceCalculator
from .performance_estimation import CBPE, DLE
