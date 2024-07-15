from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo import MongoClient, errors
from dotenv import load_dotenv
import requests, os
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
    return {
        "email": email,
        "items": [],
    }

def get_user_email():
    user = session.get('user')
    if user:
        return user.get('email')
    return None

def search_item(query, allWords=False, pageNumber=1, pageSize=20, DataType=None, format="abridged"):
    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    if DataType == "All":
        data_types = ["Branded", "Survey (FNDDS)"]
    elif DataType == "Branded":
        data_types = ["Branded"]
    elif DataType == "Survey":
        data_types = ["Survey (FNDDS)"]
    else:
        data_types = ["Custom"]

    all_items = []
    for data_type in data_types:
        params = {
            "query": query,
            "api_key": api_key,
            "pageSize": pageSize,
            "pageNumber": pageNumber,
            "requireAllWords": allWords,
            "DataType": data_type,
            "format": format
        }
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('totalHits') > 0:
                all_items.extend(data.get('foods', []))

    food_items = []
    for item in all_items:
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

        food_item = {**common_info, **subinfo}
        food_items.append(food_item)

    return food_items

# users: user info would be in items
# recipes: recipes in items
# pantry: pantry items in items
# foods: custom food items in items

@app.route('/oauth2callback', methods=['POST'])
def oauth2callback():
    code = request.json.get('code')

    client_id = os.getenv("client_id")
    client_secret = os.getenv("client_secret")
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

        email = user_info['email']
        user = users_collection.find_one({"email": email})
        if not user:
            user_data = {
                "username": user_info.get('name', email.split('@')[0]),
                "email": email,
                "google_id": user_info['sub'],
                "birthday": None,
                "height": None,
                "weight": None,
                "gender": None
            }
            try:
                users_collection.insert_one(user_data)
                pantry_data = itemify(email)
                db.pantry.insert_one(pantry_data)
            except errors.DuplicateKeyError:
                print("Duplicate key error: Username already exists.")
        else:
            session['user'] = {"email": email}
        session['user'] = {"email": email}
        return jsonify({"message": "Logged in successfully"}), 200
    else:
        return jsonify({"error": "Invalid token response"}), 400

@app.route('/current_user', methods=['GET'])
def current_user():
    user = session.get('user')
    if user:
        user_data = users_collection.find_one({"email": user['email']}, {"_id": 0})
        return jsonify(user_data), 200
    return jsonify({"error": "Not logged in"}), 401

@app.route('/onboarding', methods=['POST'])
def onboarding():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    birthday = request.json.get('birthday')
    height = request.json.get('height')
    weight = request.json.get('weight')
    gender = request.json.get('gender')


    users_collection.update_one(
        {"email": email},
        {"$set": {
            "birthday": birthday,
            "height": height,
            "weight": weight,
            "gender": gender
        }}
    )

    return jsonify({"message": "Onboarding completed"}), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/pantry', methods=['GET'])
def get_pantry():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    pantry = db.pantry.find_one({"email": email}, {"_id": 0, "items": 1})
    return jsonify(pantry["items"] if pantry else [])

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    all_words = request.args.get('allWords', 'false').lower() == 'true'
    page_number = int(request.args.get('pageNumber', 1))
    page_size = int(request.args.get('pageSize', 20))
    data_type = request.args.get('dataType')

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    sorted_items = {"Custom": [], "Branded": [], "Survey": []}
    

    
    if data_type == "Custom" or data_type == "All":
        custom_items = foods_collection.find_one({"email": email}, {"_id": 0, "items": 1})
        custom_items = custom_items.get("items", [])
        for item in custom_items:
            if query.lower() in item['description'].lower():
                sorted_items["Custom"].append(item)
    if data_type == "Branded" or data_type == "All":
        usda_items = search_item(query, allWords=all_words, pageNumber=page_number, pageSize=page_size, DataType="Branded")
        if usda_items:
            for item in usda_items:
                sorted_items["Branded"].append(item)
    if data_type == "Survey" or data_type == "All":
        usda_items = search_item(query, allWords=all_words, pageNumber=page_number, pageSize=page_size, DataType="Survey")
        if usda_items:
            for item in usda_items:
                sorted_items["Survey"].append(item)
    return jsonify(sorted_items)

@app.route('/create_new_food', methods=['POST'])
def create_item():
    data = request.get_json()
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    # Validate required fields
    required_fields = ['description', 'serving_size', 'quantity_per_unit', 'foodNutrients']
    if any(field not in data for field in required_fields):
        return jsonify({"error": "Missing fields"}), 400

    # Add to database
    new_food_item = {
        "description": data['description'],
        "serving_size": data['serving_size'],
        "quantity_per_unit": data['quantity_per_unit'],
        "foodNutrients": data['foodNutrients'],
        "ingredients": data.get('ingredients', []),
        "dataType": "Custom"
    }
    result = foods_collection.update_one(
        {"email": email},
        {"$push": {"items": new_food_item}},
        upsert=True
    )
    
    # Return the newly created food item for further actions
    return jsonify({"message": "Food item created", "food_item": new_food_item}), 200

@app.route('/add_to_pantry', methods=['POST'])
def add_to_pantry():
    data = request.get_json()
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    # Assuming 'item' contains all the necessary data
    new_pantry_item = {
        "item": data['item'],
        "quantity": data['quantity'],
        "expiryDate": data['expiryDate'],
        "cost": data['cost']
    }
    
    db.pantry.update_one(
        {"email": email},
        {"$push": {"items": new_pantry_item}},
        upsert=True
    )
    
    return jsonify({"message": "Item added to pantry"}), 200

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')
    quantity = request.json.get('quantity')

    db.pantry.update_one(
        {"email": email, "items.item.description": item["description"]},
        {"$set": {"items.$.quantity": quantity}}
    )

    return jsonify({"message": "Quantity updated successfully"}), 200

@app.route('/remove_item', methods=['POST'])
def remove_item():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')

    db.pantry.update_one(
        {"email": email},
        {"$pull": {"items": {"item.description": item["description"]}}}
    )

    return jsonify({"message": "Item removed from pantry"}), 200

@app.route('/custom_foods', methods=['GET'])
def custom_foods():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    custom_foods = foods_collection.find_one({"email": email}, {"_id": 0, "items": 1})
    return jsonify(custom_foods.get("items", []))

@app.route('/update_custom_food_ingredients', methods=['POST'])
def update_custom_food_ingredients():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')
    ingredients = request.json.get('ingredients')

    db.foods.update_one(
        {"email": email, "items.description": item["description"]},
        {"$set": {"items.$.ingredients": ingredients}}
    )

    return jsonify({"message": "Ingredients updated successfully"}), 200

@app.route('/add_custom_food', methods=['POST'])
def add_custom_food():
    email = get_user_email()
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json
    db.foods.update_one(
        {"email": email},
        {"$push": {"items": item}},
        upsert=True
    )

    return jsonify({"message": "Custom food added successfully"}), 200


if __name__ == '__main__':
    app.run(debug=True)