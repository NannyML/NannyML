.. _multiclasss-business-value-estimation:

=======================================================
Estimating Business Value for Multiclass Classification
=======================================================

This tutorial explains how to use NannyML to estimate business value for multiclass classification
models in the absence of target data. To find out how CBPE estimates performance metrics,
read the :ref:`explanation of Confidence-based Performance Estimation<performance-estimation-deep-dive>`.

.. note::
    The following example uses :term:`timestamps<Timestamp>`.
    These are optional but have an impact on the way data is chunked and results are plotted.
    You can read more about them in the :ref:`data requirements<data_requirements_columns_timestamp>`.

.. _business-value-estimation-multiclass-just-the-code:

Just The Code
-------------

.. nbimport::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cells: 1 3 4 5 7


Walkthrough
-----------

For simplicity this guide is based on a synthetic dataset where the monitored model predicts
which type of credit card product new customers should be assigned to.
Check out :ref:`Credit Card Dataset<dataset-synthetic-multiclass>` to learn more about this dataset.

In order to monitor a model, NannyML needs to learn about it from a reference dataset. Then it can monitor the data that is subject to actual analysis, provided as the analysis dataset.
You can read more about this in our section on :ref:`data periods<data-drift-periods>`.

We start by loading the dataset we'll be using:

.. nbimport::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cells: 1

.. nbtable::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cell: 2

Next we create the Confidence-based Performance Estimation
(:class:`~nannyml.performance_estimation.confidence_based.cbpe.CBPE`)
estimator. To initialize an estimator that estimates **business_value**, we specify the following
parameters:

  - **y_pred_proba:** the name of the column in the reference data that
    contains the predicted probabilities.
  - **y_pred:** the name of the column in the reference data that
    contains the predicted classes.
  - **y_true:** the name of the column in the reference data that
    contains the true classes.
  - **timestamp_column_name (Optional):** the name of the column in the reference data that
    contains timestamps.
  - **metrics:** a list of metrics to estimate. In this example we
    will estimate the ``business_value`` metric.
  - **chunk_size (Optional):** the number of observations in each chunk of data
    used to estimate performance. For more information about
    :term:`chunking<Data Chunk>` configurations check out the :ref:`chunking tutorial<chunking>`.
  - **problem_type:** the type of problem being monitored. In this example we
    will monitor a multiclass classification problem.
  - **business_value_matrix:** A matrix that specifies the value of each corresponding cell in the confusion matrix.
  - **normalize_business_value (Optional):** how to normalize the business value.
    The normalization options are:  

    * **None** : returns the total value per chunk
    * **"per_prediction"** :  returns the total value for the chunk divided by the number of observations
      in a given chunk.

  - **thresholds (Optional):** the thresholds used to calculate the alert flag. For more information about
    thresholds, check out the :ref:`thresholds tutorial<thresholds>`.

.. note::
    When calculating **business_value**, the ``business_value_matrix`` parameter is required.
    A :term:`business value matrix` is a nxn matrix that specifies the value of each cell in the confusion matrix.
    The format of the business value matrix must be specified so that each element represents the business
    value of it's respective confusion matrix element. Hence the element on the i-th row and j-column of the
    business value matrix tells us the value of the i-th target when we have predicted the j-th value.
    The target values that each column and row refer are sorted alphanumerically for both
    the confusion matrix and the business value matrices.

    The business value matrix can be provided as a list of lists or a numpy array.
    For more information about the business value matrix,
    check out the :ref:`Business Value "How it Works" page<business-value-deep-dive>`.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cells: 3

The :class:`~nannyml.performance_estimation.confidence_based.cbpe.CBPE`
estimator is then fitted using the
:meth:`~nannyml.performance_estimation.confidence_based.cbpe.CBPE.fit` method on the ``reference`` data.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cells: 4

The fitted ``estimator`` can be used to estimate performance on other data, for which performance cannot be calculated.
Typically, this would be used on the latest production data where target is missing. In our example this is
the ``analysis_df`` data.

NannyML can then output a dataframe that contains all the results. Let's have a look at the results for analysis period
only.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cells: 5

.. nbtable::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cell: 6

Apart from chunk-related data, the results data have the following columns for each metric
that was estimated:

 - **value** - the estimate of a metric for a specific chunk.
 - **sampling_error** - the estimate of the :term:`sampling error<Sampling Error>`.
 - **realized** - when **target** values are available for a chunk, the realized performance metric will also
   be calculated and included within the results.
 - **upper_confidence_boundary** and **lower_confidence_boundary** - These values show the :term:`confidence band<Confidence Band>` of the relevant metric
   and are equal to estimated value +/- 3 times the estimated :term:`sampling error<Sampling Error>`.
 - **upper_threshold** and **lower_threshold** - crossing these thresholds will raise an alert on significant
   performance change. The thresholds are calculated based on the actual performance of the monitored model on chunks in
   the **reference** partition. The thresholds are 3 standard deviations away from the mean performance calculated on
   the reference chunks.
   The thresholds are calculated during **fit** phase.
 - **alert** - flag indicating potentially significant performance change. ``True`` if estimated performance crosses
   upper or lower threshold.

These results can be also plotted. Our plots contains several key elements.

* The purple dashed step plot shows the estimated performance in each chunk of the provided data. Thick squared point
  markers indicate the middle of these chunks.

* The black vertical line splits the reference and analysis periods.

* *The low-saturated purple area* around the estimated performance in the analysis period corresponds to the
  :term:`confidence band<Confidence Band>` which is calculated as the estimated performance +/- 3 times the
  estimated :term:`Sampling Error`.

* *The red horizontal dashed lines* show upper and lower thresholds that indicate the range of
  expected performance values.

* *The red diamond-shaped point markers* in the middle of a chunk indicate that an alert has been raised.
  Alerts are caused by the estimated performance crossing the upper or lower threshold.

.. nbimport::
    :path: ./example_notebooks/Tutorial - Estimating Business Value - Multiclass Classification.ipynb
    :cells: 7

.. image:: ../../../_static/tutorials/performance_estimation/multiclass/business_value.svg

Additional information such as the chunk index range and chunk date range (if timestamps were provided) is shown in the hover for each chunk (these are
interactive plots, though only static views are included here).

Insights
--------

After reviewing the performance estimation results, we should be able to see any indications of performance change that
NannyML has detected based upon the model's inputs and outputs alone.


What's next
-----------

The :ref:`Data Drift<data-drift>` functionality can help us to understand whether data drift is causing the performance problem.
When the target values become available we can
:ref:`compared realized and estimated business value results<compare_estimated_and_realized_performance>`.
