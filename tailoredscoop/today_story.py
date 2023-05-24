import datetime

import pytz
from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Today(Base):
    __tablename__ = "today"
    id = Column(Integer, primary_key=True)
    content = Column(String(8096), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


class MySQL:
    def __init__(self, secrets):
        user = f"{secrets['mysql']['username']}:{secrets['mysql']['password']}"
        host = f"{secrets['mysql']['host']}/{secrets['mysql']['database']}"
        self.engine = create_engine(f"mysql+mysqlconnector://{user}@{host}")

        with self.engine.connect() as connection:
            connection.execute(
                text(
                    "ALTER TABLE apps.today  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            )

    def update(self, content):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        new_entry = Today(
            content=content,
            timestamp=datetime.now(pytz.utc),
        )
        session.add(new_entry)
        session.commit()
        session.close()
