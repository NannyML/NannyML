.. _how_thresholds:

===========
Thresholds
===========

Threshold basics
-----------------

The :class:`~nannyml.thresholds.Threshold` class represents a way of calculating thresholds.
Its :meth:`~nannyml.thresholds.Threshold.thresholds` method returns two values: a lower and an upper threshold value.
It takes a ``np.ndarray`` of values as a parameter. This are typically the metric or method value
calculated on reference data.

All NannyML calculators and estimators have a ``threshold`` property that allows you to set a custom threshold for
their metrics or inspect them.

When the calculator or estimator runs it will use :term:`reference data<data period>` to calculate the lower and upper
threshold values during fitting.
These values are then used during calculation or estimation to check if the
values for each chunk are breaching either the lower or upper threshold value.
If so, an alert flag will be set to ``True`` for that chunk.


Some metrics have mathematical boundaries. The ``F1`` score for example, is limited to `[0, 1]`.
To enforce these boundaries some metrics and drift methods within NannyML have lower and upper limits.
When calculating the threshold values during fitting, NannyML will check if the calculated threshold values fall within
these limits. If they don't, the breaching threshold value(s) will be overridden by the theoretical limit.

NannyML also supports disabling the lower, upper or both thresholds. We'll illustrate this in the following examples.

Constant thresholds
---------------------

The :class:`~nannyml.thresholds.ConstantThreshold` class is a very basic threshold. It is given a lower and upper value
when initialized and these will be returned as the lower and upper threshold values, independent of what reference data
is passed to it.

The :class:`~nannyml.thresholds.ConstantThreshold` can be configured using the following parameters:

- ``lower``: an optional float that sets the constant lower value. Defaults to ``None``.
                            Setting this to ``None`` disables the lower threshold.
- ``upper``: an optional float that sets the constant upper threshold value. Defaults to ``None``.
                            Setting this to ``None`` disables the upper threshold.

.. nbimport::
    :path: ./example_notebooks/How it Works - Thresholds.ipynb
    :cells: 2
    :show_output:

The ``lower`` and ``upper`` parameters have a default value of ``None``. NannyML interprets this as `no lower threshold
should be applied`.

.. nbimport::
    :path: ./example_notebooks/How it Works - Thresholds.ipynb
    :cells: 3
    :show_output:

Standard deviation thresholds
--------------------------------

The :class:`~nannyml.thresholds.StandardDeviationThreshold` class will use the mean of the data it is given as
a baseline. It will then add the standard deviation of the given data, scaled by a multiplier, to that baseline to
calculate the upper threshold value. By subtracting the standard deviation, scaled by a multiplier, from the baseline
it calculates the lower threshold value.

This is easier to illustrate in code:

.. code-block:: python

    data = np.asarray(range(10))
    baseline = np.mean(data)
    offset = np.std(data)
    upper_offset = offset * 3
    lower_offset = offset * 3
    lower_threshold, upper_threshold = baseline - lower_offset, baseline + upper_offset

The :class:`~nannyml.thresholds.StandardDeviationThreshold` can be configured using the following parameters:

- ``std_lower_multiplier``: an optional float that scales the offset for the upper threshold value. Defaults to ``3``.
- ``std_upper_multiplier``: an optional float that scales the offset for the lower threshold value. Defaults to ``3``.
- ``offset_from``: a function used to aggregate the given data.

These examples show how to create a :class:`~nannyml.thresholds.StandardDeviationThreshold`.
This first example demonstrates the default usage.

.. nbimport::
    :path: ./example_notebooks/How it Works - Thresholds.ipynb
    :cells: 4
    :show_output:

This next example shows how to configure the :class:`~nannyml.thresholds.StandardDeviationThreshold`.
Multipliers can make the offset smaller or larger, alternatives to the `mean` may be provided as well.

.. nbimport::
    :path: ./example_notebooks/How it Works - Thresholds.ipynb
    :cells: 5
    :show_output:

By providing a `None` value you can disable one or more thresholds. The following example shows how to disable the
lower threshold by setting the appropriate multiplier to `None`.

.. nbimport::
    :path: ./example_notebooks/How it Works - Thresholds.ipynb
    :cells: 6
    :show_output:

.. warning::

    The :math:`chi^2` drift detection method for categorical data does not support custom thresholds yet.
    It is currently using p-values for thresholding and replacing them by or incorporating them in the custom
    thresholding system requires further research.

    For now it will continue to function as it did before.

    When specifying a custom threshold for :math:`chi^2` in the
    :class:`~nannyml.drift.univariate.calculator.UnivariateDriftCalculator`, NannyML will log a warning message
    to clarify the custom threshold will be ignored.
