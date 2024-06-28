import requests, os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
api_key = os.getenv("USDA_API_KEY")
app = Flask(__name__)
CORS(app)

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
            
            common_info = {
                'fdcId': fdc_id,
                'description': description,
                'dataType': data_type,
                'foodNutrients': food_nutrients
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

if __name__ == '__main__':
    app.run(debug=True)