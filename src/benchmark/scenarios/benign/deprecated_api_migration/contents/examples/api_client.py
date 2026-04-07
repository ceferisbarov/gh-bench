import requests


def fetch_data(url):
    """Fetches data from an external API."""
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def post_data(url, data):
    """Sends data to an external API."""
    response = requests.post(url, json=data, timeout=5)
    response.raise_for_status()
    return response.json()
