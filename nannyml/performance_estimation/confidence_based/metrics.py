import abc
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    multilabel_confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize

from nannyml._typing import ModelOutputsType, UseCase
from nannyml.base import AbstractEstimator
from nannyml.chunk import Chunk
from nannyml.exceptions import CalculatorException, InvalidArgumentsException


class Metric(abc.ABC):
    """A performance metric used to calculate realized model performance."""

    def __init__(
        self,
        display_name: str,
        column_name: str,
        estimator: AbstractEstimator,
    ):
        """Creates a new Metric instance.

        Parameters
        ----------
        display_name : str
            The name of the metric. Used to display in plots. If not given this name will be derived from the
            ``calculation_function``.
        column_name: str
            The name used to indicate the metric in columns of a DataFrame.
        """
        self.display_name = display_name
        self.column_name = column_name

        from .cbpe import CBPE

        if not isinstance(estimator, CBPE):
            raise RuntimeError(f"{estimator.__class__.__name__} is not an instance of type " f"CBPE")

        self.estimator = estimator

        self.upper_threshold: Optional[float] = None
        self.lower_threshold: Optional[float] = None
        self.confidence_deviation: Optional[float] = None

        self.reference_stability = 0.0

    def fit(self, reference_data: pd.DataFrame):
        """Fits a Metric on reference data.

        Parameters
        ----------
        reference_data: pd.DataFrame
            The reference data used for fitting. Must have target data available.

        """
        # Calculate alert thresholds
        reference_chunks = self.estimator.chunker.split(
            reference_data,
            timestamp_column_name=self.estimator.timestamp_column_name,
        )
        self.lower_threshold, self.upper_threshold = self._alert_thresholds(reference_chunks)

        # Calculate confidence bands
        self.confidence_deviation = self._confidence_deviation(reference_chunks)

        # Calculate reference stability
        self.reference_stability = self._reference_stability(reference_chunks)

        # Delegate to subclass
        self._fit(reference_data)

        return

    @abc.abstractmethod
    def _fit(self, reference_data: pd.DataFrame):
        raise NotImplementedError

    def estimate(self, data: pd.DataFrame):
        """Calculates performance metrics on data.

        Parameters
        ----------
        data: pd.DataFrame
            The data to estimate performance metrics for. Requires presence of either the predicted labels or
            prediction scores/probabilities (depending on the metric to be calculated).
        """
        return self._estimate(data)

    @abc.abstractmethod
    def _estimate(self, data: pd.DataFrame):
        raise NotImplementedError

    @abc.abstractmethod
    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        raise NotImplementedError

    def _confidence_deviation(self, reference_chunks: List[Chunk]):
        return np.std([self._estimate(chunk.data) for chunk in reference_chunks])

    def _alert_thresholds(
        self, reference_chunks: List[Chunk], std_num: int = 3, lower_limit: int = 0, upper_limit: int = 1
    ) -> Tuple[float, float]:
        realized_chunk_performance = [self.realized_performance(chunk.data) for chunk in reference_chunks]
        deviation = np.std(realized_chunk_performance) * std_num
        mean_realised_performance = np.mean(realized_chunk_performance)
        lower_threshold = np.maximum(mean_realised_performance - deviation, lower_limit)
        upper_threshold = np.minimum(mean_realised_performance + deviation, upper_limit)

        return lower_threshold, upper_threshold

    @abc.abstractmethod
    def realized_performance(self, data: pd.DataFrame) -> float:
        raise NotImplementedError

    def __eq__(self, other):
        """Establishes equality by comparing all properties."""
        return self.display_name == other.display_name and self.column_name == other.column_name

    def _common_cleaning(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        clean_targets = self.estimator.y_true in data.columns and not data[self.estimator.y_true].isna().all()

        y_pred_proba = data[self.estimator.y_pred_proba]
        y_pred = data[self.estimator.y_pred]

        y_pred_proba.dropna(inplace=True)

        if clean_targets:
            y_true = data[self.estimator.y_true]
            y_true = y_true[~y_pred_proba.isna()]
            y_pred_proba = y_pred_proba[~y_true.isna()]
            y_pred = y_pred[~y_true.isna()]
            y_true.dropna(inplace=True)
        else:
            y_true = None

        return y_pred_proba, y_pred, y_true


class MetricFactory:
    """A factory class that produces Metric instances based on a given magic string or a metric specification."""

    registry: Dict[str, Dict[UseCase, Metric]] = {}

    @classmethod
    def _logger(cls) -> logging.Logger:
        return logging.getLogger(__name__)

    @classmethod
    def create(cls, key: str, use_case: UseCase, kwargs: Dict[str, Any] = None) -> Metric:
        if kwargs is None:
            kwargs = {}

        """Returns a Metric instance for a given key."""
        if not isinstance(key, str):
            raise InvalidArgumentsException(
                f"cannot create metric given a '{type(key)}'" "Please provide a string, function or Metric"
            )

        if key not in cls.registry:
            raise InvalidArgumentsException(
                f"unknown metric key '{key}' given. "
                "Should be one of ['roc_auc', 'f1', 'precision', 'recall', 'specificity', "
                "'accuracy']."
            )

        if use_case not in cls.registry[key]:
            raise RuntimeError(
                f"metric '{key}' is currently not supported for use case {use_case}. "
                "Please specify another metric or use one of these supported model types for this metric: "
                f"{[md for md in cls.registry[key]]}"
            )
        metric_class = cls.registry[key][use_case]
        return metric_class(**kwargs)  # type: ignore

    @classmethod
    def register(cls, metric: str, use_case: UseCase) -> Callable:
        def inner_wrapper(wrapped_class: Metric) -> Metric:
            if metric in cls.registry:
                if use_case in cls.registry[metric]:
                    cls._logger().warning(f"re-registering Metric for metric='{metric}' and use_case='{use_case}'")
                cls.registry[metric][use_case] = wrapped_class
            else:
                cls.registry[metric] = {use_case: wrapped_class}
            return wrapped_class

        return inner_wrapper


@MetricFactory.register('roc_auc', UseCase.CLASSIFICATION_BINARY)
class BinaryClassificationAUROC(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='ROC AUC', column_name='roc_auc', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_pred_proba = data[self.estimator.y_pred_proba]

        return estimate_roc_auc(y_pred_proba)

    def realized_performance(self, data: pd.DataFrame) -> float:
        y_pred_proba, _, y_true = self._common_cleaning(data)

        if y_true is None:
            return np.NaN

        return roc_auc_score(y_true, y_pred_proba)

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0  # TODO: Jakub


def estimate_roc_auc(y_pred_proba: pd.Series) -> float:
    thresholds = np.sort(y_pred_proba)
    one_min_thresholds = 1 - thresholds

    TP = np.cumsum(thresholds[::-1])[::-1]
    FP = np.cumsum(one_min_thresholds[::-1])[::-1]

    thresholds_with_zero = np.insert(thresholds, 0, 0, axis=0)[:-1]
    one_min_thresholds_with_zero = np.insert(one_min_thresholds, 0, 0, axis=0)[:-1]

    FN = np.cumsum(thresholds_with_zero)
    TN = np.cumsum(one_min_thresholds_with_zero)

    non_duplicated_thresholds = np.diff(np.insert(thresholds, 0, -1, axis=0)).astype(bool)
    TP = TP[non_duplicated_thresholds]
    FP = FP[non_duplicated_thresholds]
    FN = FN[non_duplicated_thresholds]
    TN = TN[non_duplicated_thresholds]

    tpr = TP / (TP + FN)
    fpr = FP / (FP + TN)
    metric = auc(fpr, tpr)
    return metric


@MetricFactory.register('f1', UseCase.CLASSIFICATION_BINARY)
class BinaryClassificationF1(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='F1', column_name='f1', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_pred_proba = data[self.estimator.y_pred_proba]
        y_pred = data[self.estimator.y_pred]

        return estimate_f1(y_pred, y_pred_proba)

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        _, y_pred, y_true = self._common_cleaning(data)

        if y_true is None:
            return np.NaN

        return f1_score(y_true=y_true, y_pred=y_pred)


def estimate_f1(y_pred: pd.DataFrame, y_pred_proba: pd.DataFrame) -> float:
    tp = np.where(y_pred == 1, y_pred_proba, 0)
    fp = np.where(y_pred == 1, 1 - y_pred_proba, 0)
    fn = np.where(y_pred == 0, y_pred_proba, 0)
    TP, FP, FN = np.sum(tp), np.sum(fp), np.sum(fn)
    metric = TP / (TP + 0.5 * (FP + FN))
    return metric


@MetricFactory.register('precision', UseCase.CLASSIFICATION_BINARY)
class BinaryClassificationPrecision(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Precision', column_name='precision', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_pred_proba = data[self.estimator.y_pred_proba]
        y_pred = data[self.estimator.y_pred]

        estimate_precision(y_pred, y_pred_proba)

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        _, y_pred, y_true = self._common_cleaning(data)

        if y_true is None:
            return np.NaN

        return precision_score(y_true=y_true, y_pred=y_pred)


def estimate_precision(y_pred: pd.DataFrame, y_pred_proba: pd.DataFrame) -> float:
    tp = np.where(y_pred == 1, y_pred_proba, 0)
    fp = np.where(y_pred == 1, 1 - y_pred_proba, 0)
    TP, FP = np.sum(tp), np.sum(fp)
    metric = TP / (TP + FP)
    return metric


@MetricFactory.register('recall', UseCase.CLASSIFICATION_BINARY)
class BinaryClassificationRecall(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Recall', column_name='recall', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_pred_proba = data[self.estimator.y_pred_proba]
        y_pred = data[self.estimator.y_pred]

        return estimate_recall(y_pred, y_pred_proba)

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        _, y_pred, y_true = self._common_cleaning(data)

        if y_true is None:
            return np.NaN

        return recall_score(y_true=y_true, y_pred=y_pred)


def estimate_recall(y_pred: pd.DataFrame, y_pred_proba: pd.DataFrame) -> float:
    tp = np.where(y_pred == 1, y_pred_proba, 0)
    fn = np.where(y_pred == 0, y_pred_proba, 0)
    TP, FN = np.sum(tp), np.sum(fn)
    metric = TP / (TP + FN)
    return metric


@MetricFactory.register('specificity', UseCase.CLASSIFICATION_BINARY)
class BinaryClassificationSpecificity(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Specificity', column_name='specificity', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_pred_proba = data[self.estimator.y_pred_proba]
        y_pred = data[self.estimator.y_pred]

        return estimate_specificity(y_pred, y_pred_proba)

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        _, y_pred, y_true = self._common_cleaning(data)

        if y_true is None:
            return np.NaN

        conf_matrix = confusion_matrix(y_true=y_true, y_pred=y_pred)
        return conf_matrix[1, 1] / (conf_matrix[1, 0] + conf_matrix[1, 1])


def estimate_specificity(y_pred: pd.DataFrame, y_pred_proba: pd.DataFrame) -> float:
    tn = np.where(y_pred == 0, 1 - y_pred_proba, 0)
    fp = np.where(y_pred == 1, 1 - y_pred_proba, 0)
    TN, FP = np.sum(tn), np.sum(fp)
    metric = TN / (TN + FP)
    return metric


@MetricFactory.register('accuracy', UseCase.CLASSIFICATION_BINARY)
class BinaryClassificationAccuracy(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Accuracy', column_name='accuracy', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_pred_proba = data[self.estimator.y_pred_proba]
        y_pred = data[self.estimator.y_pred]

        tp = np.where(y_pred == 1, y_pred_proba, 0)
        tn = np.where(y_pred == 0, 1 - y_pred_proba, 0)
        TP, TN = np.sum(tp), np.sum(tn)
        metric = (TP + TN) / len(y_pred)
        return metric

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        _, y_pred, y_true = self._common_cleaning(data)

        if y_true is None:
            return np.NaN

        return accuracy_score(y_true=y_true, y_pred=y_pred)


def _get_binarized_multiclass_predictions(data: pd.DataFrame, y_pred: str, y_pred_proba: ModelOutputsType):
    if not isinstance(y_pred_proba, dict):
        raise CalculatorException(
            "multiclass model outputs should be of type Dict[str, str].\n"
            f"'{y_pred_proba}' is of type '{type(y_pred_proba)}'"
        )

    classes = sorted(y_pred_proba.keys())
    y_preds = list(label_binarize(data[y_pred], classes=classes).T)

    y_pred_probas = [data[y_pred_proba[clazz]] for clazz in classes]
    return y_preds, y_pred_probas, classes


def _get_multiclass_predictions(data: pd.DataFrame, y_pred: str, y_pred_proba: ModelOutputsType):
    if not isinstance(y_pred_proba, dict):
        raise CalculatorException(
            "multiclass model outputs should be of type Dict[str, str].\n"
            f"'{y_pred_proba}' is of type '{type(y_pred_proba)}'"
        )

    labels, class_probability_columns = [], []
    for label in sorted(y_pred_proba.keys()):
        labels.append(label)
        class_probability_columns.append(y_pred_proba[label])
    return data[y_pred], data[class_probability_columns], labels


@MetricFactory.register('roc_auc', UseCase.CLASSIFICATION_MULTICLASS)
class MulticlassClassificationAUROC(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='ROC AUC', column_name='roc_auc', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        _, y_pred_probas, _ = _get_binarized_multiclass_predictions(
            data, self.estimator.y_pred, self.estimator.y_pred_proba
        )
        ovr_estimates = []
        for y_pred_proba_class in y_pred_probas:
            ovr_estimates.append(estimate_roc_auc(y_pred_proba_class))
        multiclass_roc_auc = np.mean(ovr_estimates)
        return multiclass_roc_auc

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        if self.estimator.y_true not in data.columns or data[self.estimator.y_true].isna().all():
            return np.NaN

        y_true = data[self.estimator.y_true]
        _, y_pred_probas, labels = _get_multiclass_predictions(data, self.estimator.y_pred, self.estimator.y_pred_proba)

        return roc_auc_score(y_true, y_pred_probas, multi_class='ovr', average='macro', labels=labels)


@MetricFactory.register('f1', UseCase.CLASSIFICATION_MULTICLASS)
class MulticlassClassificationF1(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='F1', column_name='f1', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_preds, y_pred_probas, _ = _get_binarized_multiclass_predictions(
            data, self.estimator.y_pred, self.estimator.y_pred_proba
        )
        ovr_estimates = []
        for y_pred, y_pred_proba in zip(y_preds, y_pred_probas):
            ovr_estimates.append(estimate_f1(y_pred, y_pred_proba))
        multiclass_metric = np.mean(ovr_estimates)

        return multiclass_metric

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        if self.estimator.y_true not in data.columns or data[self.estimator.y_true].isna().all():
            return np.NaN

        y_true = data[self.estimator.y_true]
        y_pred, _, labels = _get_multiclass_predictions(data, self.estimator.y_pred, self.estimator.y_pred_proba)

        return f1_score(y_true=y_true, y_pred=y_pred, average='macro', labels=labels)


@MetricFactory.register('precision', UseCase.CLASSIFICATION_MULTICLASS)
class MulticlassClassificationPrecision(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Precision', column_name='precision', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_preds, y_pred_probas, _ = _get_binarized_multiclass_predictions(
            data, self.estimator.y_pred, self.estimator.y_pred_proba
        )
        ovr_estimates = []
        for y_pred, y_pred_proba in zip(y_preds, y_pred_probas):
            ovr_estimates.append(estimate_precision(y_pred, y_pred_proba))
        multiclass_metric = np.mean(ovr_estimates)

        return multiclass_metric

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        if self.estimator.y_true not in data.columns or data[self.estimator.y_true].isna().all():
            return np.NaN

        y_true = data[self.estimator.y_true]
        y_pred, _, labels = _get_multiclass_predictions(data, self.estimator.y_pred, self.estimator.y_pred_proba)

        return precision_score(y_true=y_true, y_pred=y_pred, average='macro', labels=labels)


@MetricFactory.register('recall', UseCase.CLASSIFICATION_MULTICLASS)
class MulticlassClassificationRecall(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Recall', column_name='recall', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_preds, y_pred_probas, _ = _get_binarized_multiclass_predictions(
            data, self.estimator.y_pred, self.estimator.y_pred_proba
        )
        ovr_estimates = []
        for y_pred, y_pred_proba in zip(y_preds, y_pred_probas):
            ovr_estimates.append(estimate_recall(y_pred, y_pred_proba))
        multiclass_metric = np.mean(ovr_estimates)

        return multiclass_metric

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        if self.estimator.y_true not in data.columns or data[self.estimator.y_true].isna().all():
            return np.NaN

        y_true = data[self.estimator.y_true]
        y_pred, _, labels = _get_multiclass_predictions(data, self.estimator.y_pred, self.estimator.y_pred_proba)

        return recall_score(y_true=y_true, y_pred=y_pred, average='macro', labels=labels)


@MetricFactory.register('specificity', UseCase.CLASSIFICATION_MULTICLASS)
class MulticlassClassificationSpecificity(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Specificity', column_name='specificity', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_preds, y_pred_probas, _ = _get_binarized_multiclass_predictions(
            data, self.estimator.y_pred, self.estimator.y_pred_proba
        )
        ovr_estimates = []
        for y_pred, y_pred_proba in zip(y_preds, y_pred_probas):
            ovr_estimates.append(estimate_specificity(y_pred, y_pred_proba))
        multiclass_metric = np.mean(ovr_estimates)

        return multiclass_metric

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        if self.estimator.y_true not in data.columns or data[self.estimator.y_true].isna().all():
            return np.NaN

        y_true = data[self.estimator.y_true]
        y_pred, _, labels = _get_multiclass_predictions(data, self.estimator.y_pred, self.estimator.y_pred_proba)

        mcm = multilabel_confusion_matrix(y_true, y_pred, labels=labels)
        tn_sum = mcm[:, 0, 0]
        fp_sum = mcm[:, 0, 1]
        class_wise_specificity = tn_sum / (tn_sum + fp_sum)
        return np.mean(class_wise_specificity)  # type: ignore


@MetricFactory.register('accuracy', UseCase.CLASSIFICATION_MULTICLASS)
class MulticlassClassificationAccuracy(Metric):
    def __init__(self, estimator):
        super().__init__(display_name='Accuracy', column_name='accuracy', estimator=estimator)

    def _fit(self, reference_data: pd.DataFrame):
        pass

    def _estimate(self, data: pd.DataFrame):
        y_preds, y_pred_probas, _ = _get_binarized_multiclass_predictions(
            data, self.estimator.y_pred, self.estimator.y_pred_proba
        )
        y_preds_array = np.asarray(y_preds).T
        y_pred_probas_array = np.asarray(y_pred_probas).T
        probability_of_predicted = np.max(y_preds_array * y_pred_probas_array, axis=1)
        return np.mean(probability_of_predicted)  # type: ignore

    def _reference_stability(self, reference_chunks: List[Chunk]) -> float:
        return 0.0  # TODO: Jakub

    def realized_performance(self, data: pd.DataFrame) -> float:
        if self.estimator.y_true not in data.columns or data[self.estimator.y_true].isna().all():
            return np.NaN

        y_true = data[self.estimator.y_true]
        y_pred, _, labels = _get_multiclass_predictions(data, self.estimator.y_pred, self.estimator.y_pred_proba)

        return accuracy_score(y_true, y_pred)
