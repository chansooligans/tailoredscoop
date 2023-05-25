from dataclasses import dataclass
from functools import cached_property
from typing import List, Optional

import pandas as pd
from sqlalchemy import create_engine

from tailoredscoop import config


@dataclass
class Users:
    def __post_init__(self):
        self.secrets = config.setup()

    @cached_property
    def engine(self):
        user = (
            f"{self.secrets['mysql']['username']}:{self.secrets['mysql']['password']}"
        )
        host = f"{self.secrets['mysql']['host']}/{self.secrets['mysql']['database']}"
        return create_engine(f"mysql+mysqlconnector://{user}@{host}")

    # Fetch all subscribed users from the database
    def get(self, emails: Optional[List[str]] = None):
        if emails:
            query = f"""
                SELECT * FROM tailorscoop_newslettersubscription
                WHERE email IN ({", ".join([f"'{x}'" for x in emails])})
            """
        else:
            query = """
                SELECT * FROM tailorscoop_newslettersubscription
            """
        return pd.read_sql_query(query, self.engine)

    def get_range(self, start: int, size: int = 99):
        begin = start * 100
        query = f"""
            SELECT * FROM tailorscoop_newslettersubscription
            WHERE id BETWEEN {int(begin)} AND {int(begin + size)}

        """
        return pd.read_sql_query(query, self.engine)
