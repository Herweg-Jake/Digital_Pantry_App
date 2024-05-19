import requests

# global temp vars
api_key = '6Rfmv8d36afO9Ptmf0PU79WV22ZdnSaFZi5zshaO'

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