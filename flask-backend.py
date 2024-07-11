from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import requests, os, bcrypt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
app.secret_key = os.environ.get('SECRET_KEY')
mongo_uri = os.getenv("mongo_uri")
client = MongoClient(mongo_uri)
api_key = os.getenv("USDA_API_KEY")


db = client.fooding
users_collection = db.users
pantry_collection = db.pantry
foods_collection = db.food


def itemify(email):
    citem = {
        "email": email,
        "items": [],
    }
    return citem

# users: user info would be in items
# recipes: recipes in items
# pantry: pantry items in items
# foods: custom food items in items

@app.route('/oauth2callback', methods=['POST'])
def oauth2callback():
    code = request.json.get('code')
    client_id = os.environ.get('client_id')
    client_secret = os.environ.get('client_secret')
    redirect_uri = "http://localhost:3000/oauth2callback"

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    token_response = requests.post(token_url, data=token_data)
    token_response_data = token_response.json()

    if "id_token" in token_response_data:
        id_token = token_response_data["id_token"]
        user_info_url = "https://www.googleapis.com/oauth2/v3/tokeninfo"
        user_info_params = {"id_token": id_token}
        user_info_response = requests.get(user_info_url, params=user_info_params)
        user_info = user_info_response.json()
        print(user_info)

        email = user_info['email']
        user = users_collection.find_one({"email": email})
        if not user:
            user_data = {
                "username": user_info.get('name', email.split('@')[0]),
                "email": email,
                "google_id": user_info['sub']
            }
            users_collection.insert_one(user_data)
        session['user'] = {"email": email}
        return jsonify({"message": "Logged in successfully"}), 200
    else:
        return jsonify({"error": "Invalid token response"}), 400

@app.route('/current_user', methods=['GET'])
def current_user():
    user = session.get('user')
    if user:
        return jsonify(user), 200
    return jsonify({"error": "Not logged in"}), 401

"""
TODO
pantry_collection.update_one(
        {"email": email},
        {"$push": {"items": pantry_item}},
        upsert=True
    )
We need to functionalize this for adding maybe
"""


# py file for api stuff
def search_item(query, allWords=False, pageNumber=1, pageSize=20, DataType=None, format="abridged"):
    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "query": query,
        "api_key": api_key,
        "pageSize": pageSize,
        "pageNumber": pageNumber,
        "requireAllWords": allWords,
        "DataType": DataType,
        "format": format
    }
    response = requests.get(base_url, params=params)

    if response.status_code != 200:
        return False

    data = response.json()
    if data.get('totalHits') == 0:
        print('TODO -- FIX TOTALHITS')
        return None
    
    food_items = []
    unsorted_foods = data.get('foods', [])
    email = session.get('user', {}).get('email')
    if email:
        custom_items = foods_collection.find_one({"email": email}, {"_id": 0, "items": 1})
        custom_items = custom_items.get("items", [])
    for item in unsorted_foods:
        fdc_id = item.get('fdcId')
        description = item.get('description')
        data_type = item.get('dataType')
        food_nutrients = item.get('foodNutrients', [])
        filtered = [nutrient for nutrient in food_nutrients if nutrient['value'] > 0.5]
        
        common_info = {
            'fdcId': fdc_id,
            'description': description,
            'dataType': data_type,
            'foodNutrients': filtered
        }
        
        if data_type == 'Branded':
            subinfo = {
                'brandOwner': item.get('brandOwner'),
                'brandName': item.get('brandName'),
                'ingredients': item.get('ingredients'),
                'servingSize': item.get('servingSize'),
                'servingSizeUnit': item.get('servingSizeUnit'),
                'householdServingFullText': item.get('householdServingFullText'),
                'gtinUpc': item.get('gtinUpc'),
                'foodCategory': item.get('foodCategory'),
                'packageWeight': item.get('packageWeight'),
                'publishedDate': item.get('publishedDate'),
                'modifiedDate': item.get('modifiedDate')
            }
        elif data_type == 'Survey (FNDDS)':
            subinfo = {
                'additionalDescriptions': item.get('additionalDescriptions'),
                'foodCategory': item.get('foodCategory'),
                'foodCode': item.get('foodCode'),
                'publishedDate': item.get('publishedDate'),
                'finalFoodInputFoods': item.get('finalFoodInputFoods', []),
                'foodMeasures': item.get('foodMeasures', [])
            }
    
    return common_info + subinfo

# TODO fix the quantity amount, the user should be able to be prompted for expiry, cost and etc from the addition instead of auto-push
@app.route('/create_new_food', methods=['POST'])
def create_item():
    name = request.json.get('name')
    serving_size = request.json.get('servingSize')
    quantity_per_unit = request.json.get('quantityPerUnit')
    mandatory_nutrients = request.json.get('mandatoryNutrients')
    optional_nutrients = request.json.get('optionalNutrients', [])
    ingredients = request.json.get('ingredients', [])
    expiry_date = request.json.get('expiryDate')

    if not name or not serving_size or not quantity_per_unit or not mandatory_nutrients:
        return jsonify({"error": "Missing input variables"}), 401
    
    email = session.get('user', {}).get('email')
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    # Ensure mandatory_nutrients and optional_nutrients are lists
    if not isinstance(mandatory_nutrients, list):
        mandatory_nutrients = [mandatory_nutrients]
    if not isinstance(optional_nutrients, list):
        optional_nutrients = [optional_nutrients]

    # Combine mandatory and optional nutrients
    food_nutrients = mandatory_nutrients + optional_nutrients

    # Create the food item
    food_item = {
        "description": name,
        "serving_size": serving_size,
        "quantity_per_unit": quantity_per_unit,
        "foodNutrients": food_nutrients,
        "ingredients": ingredients,
        "dataType": "Custom"
    }

    # Add the food item to the user's custom foods collection
    foods_collection.update_one(
        {"email": email},
        {"$push": {"items": food_item}},
        upsert=True
    )

    return jsonify({"message": "Food added to user's custom foods", "food_item": food_item}), 200


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    all_words = request.args.get('allWords', 'false').lower() == 'true'
    page_number = int(request.args.get('pageNumber', 1))
    page_size = int(request.args.get('pageSize', 20))
    data_type = request.args.get('DataType', None)

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    sorted_items = {}
    if data_type == "Custom":
        email = session.get('user', {}).get('email')
        custom_items = []
        if email:
            custom_items = foods_collection.find_one({"email": email}, {"_id": 0, "items": 1})
            custom_items = custom_items.get("items", [])
        sorted_items["Custom"] = custom_items
    else:
        sorted_items = search_item(query, allWords=all_words, pageNumber=page_number, pageSize=page_size, DataType=data_type)
        if sorted_items is None:
            sorted_items = {}

        email = session.get('user', {}).get('email')
        custom_items = []
        if email:
            custom_items = foods_collection.find_one({"email": email}, {"_id": 0, "items": 1})
            custom_items = custom_items.get("items", [])

        sorted_items["Custom"] = custom_items

    return jsonify(sorted_items)


# updates based on the '-' button
@app.route('/add_to_pantry', methods=['POST'])
def add_to_pantry():
    email = session.get('user', {}).get('email')
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')
    quantity = request.json.get('quantity')
    expiryDate = request.json.get('expiryDate')
    measure = request.json.get('measure')

    if not item or not quantity or not expiryDate or not measure:
        print("Missing data:", {
            "item": item,
            "quantity": quantity,
            "expiryDate": expiryDate,
            "measure": measure
        })
        return jsonify({"error": "Item, quantity, measure, and expiry date are required"}), 400

    pantry_item = {
        "item": item,
        "quantity": int(quantity),
        "expiryDate": expiryDate,
        "measure": measure
    }

    pantry_collection.update_one(
        {"email": email},
        {"$push": {"items": pantry_item}},
        upsert=True
    )

    return jsonify({"message": "Item added to pantry"}), 200

# updates based on the '-' button
@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    email = session.get('user', {}).get('email')
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')
    increment = request.json.get('increment')

    if not item or increment is None:
        return jsonify({"error": "Item and increment flag are required"}), 400

    pantry = pantry_collection.find_one({"email": email})
    if not pantry:
        return jsonify({"error": "Pantry not found"}), 404

    for pantry_item in pantry.get('items', []):
        if pantry_item['item']['fdcId'] == item['fdcId']:
            new_quantity = pantry_item['quantity'] + (1 if increment else -1)
            if new_quantity <= 0:
                return jsonify({"error": "Quantity cannot be less than 1"}), 400
            pantry_item['quantity'] = new_quantity
            break

    pantry_collection.update_one(
        {"email": email},
        {"$set": {"items": pantry['items']}}
    )

    return jsonify({"message": "Quantity updated successfully"}), 200

#removes item from the pantry
@app.route('/remove_item', methods=['POST'])
def remove_item():
    email = session.get('user', {}).get('email')
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')

    if not item:
        return jsonify({"error": "Item is required"}), 400

    pantry_collection.update_one(
        {"email": email},
        {"$pull": {"items": {"item.fdcId": item['fdcId']}}}
    )

    return jsonify({"message": "Item removed from pantry"}), 200

# the registering of new users, each should be passed info
@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')
    weight = request.json.get('weight')
    height = request.json.get('height')
    age = request.json.get('age')
    gender = request.json.get('gender')

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "User already exists"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user_data = {
        "username": username,
        "email": email,
        "password": hashed_password,
        "weight": weight,
        "height": height,
        "age": age,
        "gender": gender
    }

    users_collection.insert_one(user_data)

    # Create pantry for the user
    pantry_data = {
        "email": email,
        "items": []
    }
    pantry_collection.insert_one(pantry_data)

    return jsonify({"message": "User registered successfully"}), 201


# returns the session log in as the user, a bit buggin need to fix more
@app.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')
    user = users_collection.find_one({"email": email})

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        session['user'] = {"email": email}
        return jsonify({"message": "Logged in successfully"}), 200

    return jsonify({"error": "Invalid credentials"}), 401

# dont even use this lol
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "Logged out successfully"}), 200


# basically add to pantry but just returns list
@app.route('/pantry', methods=['GET'])
def get_pantry():
    email = session.get('user', {}).get('email')
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    pantry = pantry_collection.find_one({"email": email})
    print(len(pantry))
    if pantry:
        return jsonify(pantry.get("items", [])), 200

    return jsonify({"error": "Pantry not found"}), 404


if __name__ == '__main__':
    app.run(debug=True)