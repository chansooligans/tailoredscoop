import logging
import os
from distutils import dir_util
from pathlib import Path

import pytest
import tqdm


def nop(it, *a, **k):
    return it


tqdm.tqdm = nop

# disable_loggers = ["tailoredscoop.[module_name]"]
# def pytest_configure():
#     for logger_name in disable_loggers:
#         logger = logging.getLogger(logger_name)
#         logger.disabled = True
