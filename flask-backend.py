from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import requests, os, bcrypt

load_dotenv()
mongo_uri = os.getenv("mongo_uri")
api_key = os.getenv("USDA_API_KEY")
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

client = MongoClient(mongo_uri)
db = client['fooding']
users_collection = db.users
pantry_collection = db.pantry

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

    if response.status_code == 200:
        data = response.json()
        if data.get('totalHits') == 0:
            return None
        
        foods = data.get('foods', [])
        
        branded_items = []
        survey_items = []
        sr_legacy_items = []
        foundation_items = []

        for item in foods:
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
                branded_items.append({
                    **common_info,
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
                })
            elif data_type == 'Survey (FNDDS)':
                survey_items.append({
                    **common_info,
                    'additionalDescriptions': item.get('additionalDescriptions'),
                    'foodCategory': item.get('foodCategory'),
                    'foodCode': item.get('foodCode'),
                    'publishedDate': item.get('publishedDate')
                })
            elif data_type == 'SR Legacy':
                sr_legacy_items.append({
                    **common_info,
                    'scientificName': item.get('scientificName'),
                    'foodCategory': item.get('foodCategory'),
                    'publishedDate': item.get('publishedDate'),
                    'ndbNumber': item.get('ndbNumber')
                })
            elif data_type == 'Foundation':
                foundation_items.append({
                    **common_info,
                    'scientificName': item.get('scientificName'),
                    'foodCategory': item.get('foodCategory'),
                    'publishedDate': item.get('publishedDate'),
                    'ndbNumber': item.get('ndbNumber'),
                    'mostRecentAcquisitionDate': item.get('mostRecentAcquisitionDate')
                })
            else:
                print(f"Unknown data type: {data_type}")

        sorted_items = {
            "Branded": branded_items,
            "Survey": survey_items,
            "SR_Legacy": sr_legacy_items,
            "Foundation": foundation_items
        }
        
        return sorted_items
    else:
        return None




@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    all_words = request.args.get('allWords', 'false').lower() == 'true'
    page_number = int(request.args.get('pageNumber', 1))
    page_size = int(request.args.get('pageSize', 20))
    data_type = request.args.get('DataType', None)

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    sorted_items = search_item(query, allWords=all_words, pageNumber=page_number, pageSize=page_size, DataType=data_type)
    if sorted_items is None:
        return jsonify({"message": "No results found"}), 404

    return jsonify(sorted_items)

@app.route('/add_to_pantry', methods=['POST'])
def add_to_pantry():
    email = session.get('user', {}).get('email')
    if not email:
        return jsonify({"error": "Not logged in"}), 401

    item = request.json.get('item')
    quantity = request.json.get('quantity')
    expiryDate = request.json.get('expiryDate')

    if not item or not quantity or not expiryDate:
        return jsonify({"error": "Item, quantity, and expiry date are required"}), 400

    pantry_item = {
        "item": item,
        "quantity": quantity,
        "expiryDate": expiryDate
    }

    pantry_collection.update_one(
        {"email": email},
        {"$push": {"items": pantry_item}},
        upsert=True
    )

    return jsonify({"message": "Item added to pantry"}), 200



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

@app.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')
    user = users_collection.find_one({"email": email})

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        session['user'] = {"email": email}
        return jsonify({"message": "Logged in successfully"}), 200

    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/current_user', methods=['GET'])
def current_user():
    user = session.get('user')
    if user:
        return jsonify(user), 200
    return jsonify({"error": "Not logged in"}), 401

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
