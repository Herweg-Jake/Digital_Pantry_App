from dotenv import load_dotenv
from pymongo import MongoClient
import os

load_dotenv()
conn_string = os.getenv("mongo_uri")

client = MongoClient(conn_string)
db = client['fooding']
users_collection = db["users"]
pantry_collection = db["pantry"]

# Delete users without an email
users_without_email = users_collection.find({"email": {"$exists": False}})
for user in users_without_email:
    print("Deleting user without email:", user)
    users_collection.delete_one({"_id": user["_id"]})

# List all documents in the users collection
users = users_collection.find()
print("Items in 'users' collection:")
for user in users:
    print(user)
    if 'email' in user:
        user_pantry = pantry_collection.find_one({"email": user["email"]})
        print("Pantry items for", user["email"], ":")
        if user_pantry:
            for item in user_pantry.get("items", []):
                print(item)
        else:
            print("No pantry found for this user.")
    else:
        print("No email found for this user.")

client.close()
