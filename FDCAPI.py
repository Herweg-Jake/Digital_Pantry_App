import requests

# global temp vars
api_key = '6Rfmv8d36afO9Ptmf0PU79WV22ZdnSaFZi5zshaO'


def search(food_item):
    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "query": food_item,
        "api_key": api_key,
        "pageSize": 5  # return results
    }
    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        # response -> JSON
        return search_results(response.json())
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return False