import logging
from dataclasses import dataclass


@dataclass
class Logger:
    """Object for loggers"""

    def setup_logger(self):
        logger = logging.getLogger("tailoredscoops")
        logger.setLevel(logging.DEBUG)
        if logger.hasHandlers():
            return
        else:
            fh = logging.FileHandler("./logs/log.log")
            fh.setLevel(logging.DEBUG)

            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)

            formatter = logging.Formatter(
                "\n%(asctime)s - %(name)s - %(levelname)s - %(funcName)20s() | %(message)s"
            )

            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            logger.addHandler(fh)
            logger.addHandler(ch)
