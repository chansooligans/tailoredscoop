import datetime
import logging
from dataclasses import dataclass

import pandas as pd
import pymongo


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
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)20s() | %(message)s"
            )

            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            logger.addHandler(fh)
            logger.addHandler(ch)


@dataclass
class RecipientList:
    db: pymongo.database.Database

    @property
    def mongodb_query(self):
        return {
            "created_at": {
                "$gte": datetime.datetime.combine(
                    datetime.date.today(), datetime.datetime.min.time()
                ),
            }
        }

    def get_sent(self, query):
        return list(self.db.sent.find(query, {"email": 1, "_id": 0}))

    def filter_sent(self, df_users):
        sent = self.get_sent(self.mongodb_query)
        if sent:
            df_sent = pd.DataFrame(sent)["email"]
            df_users = df_users.loc[~df_users["email"].isin(df_sent)]
        return df_users
