from dotenv import load_dotenv
from pymongo import MongoClient
import os

load_dotenv()
conn_string = os.getenv("mongo_uri")

client = MongoClient(conn_string)
print(client)
db = client['fooding']
users_collection = db["users"]
pantry_collection = db["pantry"]
recipes_collection = db["recipes"]
food_collection = db["food"]
# archived food collection ^^^
print(users_collection)


# List all collections in the specified database
collections = db.list_collection_names()
print("Collections in database:", collections)

client.close()