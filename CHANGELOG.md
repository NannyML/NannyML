# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.2] - 2022-08-17

### Changed

- Swapped out ASCII art library from 'art' to 'PyFiglet' because the former was not yet present in conda-forge.

### Fixed

- Some leftover parameter was forgotten during cleanup, breaking CLI functionality
- CLI progressbar was broken due to a boolean check with task ID 0.


## [0.5.1] - 2022-08-16

### Added

- Added simple CLI implementation to support automation and MLOps toolchain use cases. Supports reading/writing to
  cloud storage using S3, GCS, ADL, ABFS and AZ protocols. Containerized version available at
  [dockerhub](https://hub.docker.com/repository/docker/nannyml/nannyml).

### Changed

- `make clean` now also clears `__pycache__`
- Fixed some inconsistencies in docstrings (they still need some additional love though)

## [0.5.0] - 2022-07-07

### Changed
- Replaced the whole Metadata system by a more intuitive approach.

### Fixed
- Fix docs [(#87)](https://github.com/NannyML/nannyml/issues/79) and [(#89)](https://github.com/NannyML/nannyml/issues/89), thanks [@NeoKish](https://github.com/NeoKish)
- Fix confidence bounds for binary settings [(#86)](https://github.com/NannyML/nannyml/issues/86), thanks [@rfrenoy](https://github.com/rfrenoy)
- Fix README [(#87)](https://github.com/NannyML/nannyml/issues/79), thanks [@NeoKish](https://github.com/NeoKish)
- Fix index misalignment on calibration [(#79)](https://github.com/NannyML/nannyml/issues/79)
- Fix Poetry dev-dependencies issues [(#78)](https://github.com/NannyML/nannyml/issues/78), thanks [@rfrenoy](https://github.com/rfrenoy)
- Fix incorrect documentation links [(#76)](https://github.com/NannyML/nannyml/issues/76), thanks [@SoyGema](https://github.com/SoyGema)

## [0.4.1] - 2022-05-19

### Added
- Added limited support for ``regression`` use cases: create or extract ``RegressionMetadata`` and use it for drift
  detection. Performance estimation and calculation require more research.

### Changed
- ``DefaultChunker`` splits into 10 chunks of equal size.
- ``SizeBasedChunker`` no longer drops incomplete last chunk by default, but this is now configurable behavior.

## [0.4.0] - 2022-05-13

### Added
- Added support for new metrics in the Confidence Based Performance Estimator (CBPE). It now estimates ``roc_auc``,
  ``f1``, ``precision``, ``recall`` and ``accuracy``.
- Added support for **multiclass classification**. This includes
  - Specifying ``multiclass classification metadata`` + support in automated metadata extraction (by introducing a
    ``model_type`` parameter).
  - Support for all ``CBPE`` metrics.
  - Support for realized performance calculation using the ``PerformanceCalculator``.
  - Support for all types of drift detection (model inputs, model output, target distribution).
  - A new synthetic toy dataset.

### Changed
- Removed the ``identifier`` property from the ``ModelMetadata`` class. Joining ``analysis`` data and
  ``analysis target`` values should be done upfront or index-based.
- Added an ``exclude_columns`` parameter to the ``extract_metadata`` function. Use it to specify the columns that should
  not be considered as model metadata or features.
- All ``fit`` methods now return the fitted object. This allows chaining ``Calculator``/``Estimator`` instantiation
  and fitting into a single line.
- Custom metrics are no longer supported in the ``PerformanceCalculator``. Only the predefined metrics remain supported.
- Big documentation revamp: we've tweaked overall structure, page structure and incorporated lots of feedback.
- Improvements to consistency and readability for the 'hover' visualization in the step plots, including consistent
  color usage, conditional formatting, icon usage etc.
- Improved indication of "realized" and "estimated" performance in all ``CBPE`` step plots
  (changes to hover, axes and legends)

### Fixed
- Updated homepage in project metadata
- Added missing metadata modification to the *quickstart*
- Perform some additional check on reference data during preprocessing
- Various documentation suggestions [(#58)](https://github.com/NannyML/nannyml/issues/58)

## [0.3.2] - 2022-05-03

### Fixed
- Deal with out-of-time-order data when chunking
- Fix reversed Y-axis and plot labels in continuous distribution plots

## [0.3.1] - 2022-04-11
### Changed
- Publishing to PyPi did not like raw sections in ReST, replaced by Markdown version.

## [0.3.0] - 2022-04-08
### Added
- Added support for both predicted labels and predicted probabilities in ``ModelMetadata``.
- Support for monitoring model performance metrics using the ``PerformanceCalculator``.
- Support for monitoring target distribution using the ``TargetDistributionCalculator``

### Changed
- Plotting will default to using step plots.
- Restructured the ``nannyml.drift`` package and subpackages. *Breaking changes*!
- Metadata completeness check will now fail when there are features of ``FeatureType.UNKNOWN``.
- Chunk date boundaries are now calculated differently for a ``PeriodBasedChunker``, using the
  theoretical period for boundaries as opposed to the observed boundaries within the chunk observations.
- Updated version of the ``black`` pre-commit hook due to breaking changes in its ``click`` dependency.
- The *minimum chunk size* will now be provided by each individual ``calculator`` / ``estimator`` / ``metric``,
  allowing for each of them to warn the end user when chunk sizes are suboptimal.

### Fixed
- Restrict version of the ``scipy`` dependency to be ``>=1.7.3, <1.8.0``. Planned to be relaxed ASAP.
- Deal with missing values in chunks causing ``NaN`` values when concatenating.
- Crash when estimating CBPE without a target column present
- Incorrect label in ``ModelMetadata`` printout

## [0.2.1] - 2022-03-22
### Changed
- Allow calculators/estimators to provide appropriate ``min_chunk_size`` upon splitting into ``chunks``.

### Fixed
- Data reconstruction drift calculation failing when there are no categorical or continuous features
  [(#36)](https://github.com/NannyML/nannyml/issues/36)
- Incorrect scaling on continuous feature distribution plot [(#39)](https://github.com/NannyML/nannyml/issues/39)
- Missing ``needs_calibration`` checks before performing score calibration in CBPE
- Fix crash on chunking when missing target values in reference data

## [0.2.0] - 2022-03-03
### Added
- Result classes for Calculators and Estimators.
### Changed
- Updated the documentation to reflect the changes introduced by result classes,
  specifically to plotting functionality.
- Add support for imputing of missing values in the ``DataReconstructionDriftCalculator``.
### Removed
- ``nannyml.plots.plots`` was removed.
  Plotting is now meant to be done using ``DriftResult.plot()`` or ``EstimatorResult.plot()``.


## [0.1.1] - 2022-03-03
### Fixed
- Fixed an issue where data reconstruction drift calculation also used model predictions during decomposition.


## [0.1.0] - 2022-03-03
### Added
- Chunking base classes and implementations
- Metadata definitions and utilities
- Drift calculator base classes and implementations
  - Univariate statistical drift calculator
  - Multivariate data reconstruction drift calculator
- Drifted feature ranking base classes and implementations
  - Alert count based ranking
- Performance estimator base classes and implementations
  - Certainty based performance estimator
- Plotting utilities with support for
  - Stacked bar plots
  - Line plots
  - Joy plots
- Documentation
  - Quick start guide
  - User guides
  - Deep dives
  - Example notebooks
  - Technical reference documentation
