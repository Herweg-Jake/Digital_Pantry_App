import requests, json, os, pymongo
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
api_key = os.getenv("USDA_API_KEY")

client = pymongo.MongoClient(mongo_uri)
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client.fooding
users_collection = db["users"]
pantry_collection = db["pantry"]
recipes_collection = db["recipes"]
custom_items_collection = db["custom_items"]
food_collection = db["food"]


# INDEXING:
users_collection.create_index("username", unique=True)
pantry_collection.create_index([("user_id", 1), ("item_id", 1)])
recipes_collection.create_index("user_id")
custom_items_collection.create_index("user_id")
food_collection.create_index("fdc_id", unique=True)

print("Collections and indexes have been created.")
test_user = '664d3882485b1f43c45fc3eb'


def find_details(id):
    response = requests.get(f"https://api.nal.usda.gov/fdc/v1/food/{id}", params={"api_key": api_key})
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch details: {response.status_code}")
        return None

def search_item(query, allWords=False, pageNumber=1, pageSize=5):
    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "query": query,
        "api_key": api_key,
        "pageSize": pageSize,
        "pageNumber": pageNumber,
        "requireAllWords": allWords,
    }
    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data.get('totalHits') == 0:
            return None

        foods = data.get('foods', [])

        search_criteria = [
            data['foodSearchCriteria'].get('query'),
            data['foodSearchCriteria'].get('pageNumber'),
            data['foodSearchCriteria'].get('pageSize'),
            data['foodSearchCriteria'].get('requireAllWords'),
            data.get('currentPage'),
            data.get('totalPages')
        ]

        return foods, search_criteria
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return False

def process_food_item(food_item):
    data_type = food_item.get("dataType", "").lower()

    common_fields = {
        "fdcId": food_item.get("fdcId"),
        "description": food_item.get("description"),
        "dataType": food_item.get("dataType"),
        "foodCategory": food_item.get("foodCategory")
    }
    nutrients = [
        {
            "nutrientId": nutrient.get("nutrientId"),
            "nutrientName": nutrient.get("nutrientName"),
            "unitName": nutrient.get("unitName"),
            "value": nutrient.get("value")
        }
        for nutrient in food_item.get("foodNutrients", [])
        if nutrient.get("value", 0) >= 0.01
    ]

    specific_fields = {}
    if data_type in ["foundation", "sr legacy"]:
        specific_fields["foundation"] = {
            "ndbNumber": food_item.get("ndbNumber")
        }
    elif data_type == "branded":
        specific_fields["branded"] = {
            "brandOwner": food_item.get("brandOwner"),
            "ingredients": food_item.get("ingredients"),
            "marketCountry": food_item.get("marketCountry"),
            "packageWeight": food_item.get("packageWeight"),
            "servingSize": food_item.get("servingSize"),
            "servingSizeUnit": food_item.get("servingSizeUnit")
        }
    elif data_type == "survey (fndds)":
        specific_fields["survey"] = {
            "foodCode": food_item.get("foodCode"),
            "portions": food_item.get("foodPortions", []),
            "finalFoodInputFoods": food_item.get("finalFoodInputFoods", []),
            "foodMeasures": [
                {
                    "disseminationText": measure.get("disseminationText"),
                    "gramWeight": measure.get("gramWeight"),
                    "measureUnitAbbreviation": measure.get("measureUnitAbbreviation"),
                    "measureUnitName": measure.get("measureUnitName")
                }
                for measure in food_item.get("foodMeasures", [])
            ]
        }

    obj = {
        **common_fields,
        "nutrients": nutrients,
        "measures": specific_fields
    }

    return obj

# foods, search_query = search_item('chocolate milk', True, 1, 10)