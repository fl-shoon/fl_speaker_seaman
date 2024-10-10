import requests
from etc.define import *

class GetData:
    def __init__(self):
        self.token = None
        self.fetch_auth_token()

    def fetch_auth_token(self):
        headers = {"uid": DEVICE_ID}
        response = requests.post(f"{SERVER_URL}/fetch_auth_token", headers=headers)
        if response.status_code == 200:
            self.token = response.json()['token']
            logger.info(f"Authentication token has been fetched: {self.token}")
        else:
            logger.error(f"Failed to get token: {response.text}")

    def fetch_schedule(self):
        if self.token:
            headers = {"Authorization": self.token}
            response = requests.get(f"{SERVER_URL}/fetch_schedule", headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch schedule: {response.text}")