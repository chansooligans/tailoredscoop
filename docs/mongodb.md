# MongoDB

Install Steps:

- sudo apt update
- sudo apt install mongodb
- sudo systemctl start mongodb
- sudo systemctl status mongodb
- poetry add pymongo

```
from pymongo import MongoClient

# Create a MongoDB client
client = MongoClient(secrets["mongodb"]["url"])

# Access a database
db = client.mydatabase

# Access a collection
collection = db.mycollection

# Perform operations on the collection
# For example, insert a document
document = {"name": "John", "age": 30}
collection.insert_one(document)

# Close the MongoDB connection
client.close()

```