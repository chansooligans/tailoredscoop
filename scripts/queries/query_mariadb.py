# %%
from tailoredscoop import config
import pandas as pd
from sqlalchemy import create_engine

secrets = config.setup()

# %%
user = secrets['mysql']['username']
password = secrets['mysql']['password']
host = secrets['mysql']['host']
database = secrets['mysql']['database']
engine = create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{database}')

# %%
query = 'SELECT * FROM tailorscoop_newslettersubscription'
df = pd.read_sql_query(query, engine)

# %%
df
# %%
