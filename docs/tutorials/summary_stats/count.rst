.. _sum_stats_count:

==========
Rows Count
==========

Just The Code
-------------

.. nbimport::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cells: 1 3 4 6

Walkthrough
-----------

The Row Count calculation is straightforward.
For each :term:`chunk<Data Chunk>` NannyML calculates the row count for the selected dataframe.
The resulting values from the reference :ref:`data<data-drift-periods>` chunks are used to calculate the
alert :term:`thresholds<Threshold>`. The row count results from the analysis chunks are
compared against those thresholds and generate alerts if applicable.

We begin by loading the :ref:`synthetic car loan dataset<dataset-synthetic-binary-car-loan>` provided by the NannyML package.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cells: 1

.. nbtable::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cell: 2

The :class:`~nannyml.stats.count.calculator.SummaryStatsRowCountCalculator` class implements
the functionality needed for row count calculations.
We need to instantiate it with appropriate *optional* parameters:

- The name of the column containing the observation timestamps.
- A chunking approach or a predefined chunker. If neither is provided, the default
  chunker creating 10 chunks will be used.
- A threshold strategy to modify the default one. See available threshold options
  :ref:`here<thresholds>`.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cells: 3

Next, the :meth:`~nannyml.base.AbstractCalculator.fit` method needs
to be called on the reference data, which provides the baseline that the analysis data will be
compared with for :term:`alert<Alert>` generation. Then the
:meth:`~nannyml.base.AbstractCalculator.calculate` method will
calculate the data quality results on the data provided to it.

The results can be filtered to only include a certain data period, method or column by using the ``filter`` method.
You can evaluate the result data by converting the results into a `DataFrame`,
by calling the :meth:`~nannyml.base.AbstractResult.to_df` method.
By default this will return a `DataFrame` with a multi-level index. The first level represents the column, the second level
represents resulting information such as the data quality metric values or the alert thresholds.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cells: 4

.. nbtable::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cell: 5

More information on accessing the information contained in the
:class:`~nannyml.stats.count.result.Result`
can be found on the :ref:`working_with_results` page.

The next step is visualizing the results, which is done using the
:meth:`~nannyml.stats.count.result.Result.plot` method.
It is recommended to filter results for each column and plot separately.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Stats - Count.ipynb
    :cells: 6

.. image:: /_static/tutorials/stats/count.svg


Insights
--------

We see that when we use a monthly chunking strategy we have too few data points for October 2018.


What Next
---------

We can also inspect the dataset for other Summary Statistics such as :ref:`sum_stats_avg`.
We can also inspect the dataset using :ref:`Data Quality<data-quality>`
functionality provided by NannyML.
Last but not least, we can look for any :term:`Data Drift` present in the dataset using
:ref:`data-drift` functionality of NannyML.
