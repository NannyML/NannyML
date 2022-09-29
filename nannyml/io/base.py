#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

import logging
import re
from abc import ABC, abstractmethod
from pathlib import PurePath
from typing import Any, Callable, Dict, Tuple
from urllib.parse import urlsplit

import pandas as pd

from nannyml._typing import Result
from nannyml.exceptions import InvalidArgumentsException, ReaderException, WriterException

HTTP_PROTOCOLS = ['http', 'https']
CLOUD_PROTOCOLS = ['s3', 'gcs', 'gs', 'adl', 'abfs', 'abfss']


class Writer(ABC):
    """Base class for writing out results"""

    @property
    def _logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def write(self, result: Result, **kwargs) -> Any:
        if result is None:
            raise InvalidArgumentsException("Trying to write 'None'")

        if kwargs is None:
            kwargs = {}

        try:
            self._write(result, **kwargs)
        except Exception as exc:
            raise WriterException(f"Failed writing data. \n{str(exc)}")

    @abstractmethod
    def _write(self, result: Result, **kwargs):
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Writer and it must implement the _write method"
        )


class WriterFactory:
    """A factory class that produces Mapper instances for a given Result subclass."""

    registry: Dict[str, Writer] = {}

    @classmethod
    def _logger(cls) -> logging.Logger:
        return logging.getLogger(__name__)

    @classmethod
    def create(cls, key, kwargs: Dict[str, Any] = None) -> Writer:
        """Returns a Writer instance for a given string."""

        if kwargs is None:
            kwargs = {}

        if key not in cls.registry:
            raise InvalidArgumentsException(
                f"unknown key '{key}' given. " f"Currently registered keys are: {list(cls.registry.keys())}"
            )

        writer_class = cls.registry[key]
        return writer_class(**kwargs)  # type: ignore

    @classmethod
    def register(cls, key) -> Callable:
        def inner_wrapper(wrapped_class: Writer) -> Writer:
            if key in cls.registry:
                cls._logger().warning(f"re-registering Writer for key='{key}'")
            cls.registry[key] = wrapped_class
            return wrapped_class

        return inner_wrapper


class Reader(ABC):
    """Base class for reading data"""

    @property
    def _logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    def read(self) -> pd.DataFrame:
        try:
            return self._read()
        except Exception as exc:
            raise ReaderException(f"Failed reading data. \n{str(exc)}")

    @abstractmethod
    def _read(self) -> pd.DataFrame:
        raise NotImplementedError(
            f"'{self.__class__.__name__}' is a subclass of Reader and it must implement the _read method"
        )


def get_protocol_and_path(filepath: str) -> Tuple[str, str]:
    if re.match(r"^[a-zA-Z]:[\\/]", filepath) or re.match(r"^[a-zA-Z\d]+://", filepath) is None:
        return "file", filepath

    parsed_path = urlsplit(filepath)
    protocol = parsed_path.scheme or "file"
    path = parsed_path.path

    if protocol in HTTP_PROTOCOLS:
        return protocol, path

    if protocol == "file":
        windows_path = re.match(r"^/([a-zA-Z])[:|]([\\/].*)$", path)
        if windows_path:
            path = ":".join(windows_path.groups())

    if parsed_path.netloc:
        if protocol in CLOUD_PROTOCOLS:
            host_with_port = parsed_path.netloc.rsplit("@", 1)[-1]
            host = host_with_port.rsplit(":", 1)[0]
            path = host + path

    return protocol, path


def get_filepath_str(path: PurePath, protocol: str) -> str:
    path_str = path.as_posix()
    if protocol in HTTP_PROTOCOLS:
        path_str = "".join((protocol, "://", path_str))
    return path_str
