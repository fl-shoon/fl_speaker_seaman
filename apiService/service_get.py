import requests
from etc.define import logger, SPEAKER_ID, SERVER_URL

class GetData:
    def __init__(self):
        self.token = None
        self.speaker_id = SPEAKER_ID 
        self.server_url = SERVER_URL
        self.fetch_auth_token()

    def fetch_auth_token(self):
        headers = {"uid": self.speaker_id}
        response = requests.post(f"{self.server_url}/fetch_auth_token", headers=headers)
        if response.status_code == 200:
            self.token = response.json()['token']
            logger.info(f"Authentication token has been fetched: {self.token}")
        else:
            logger.error(f"Failed to get token: {response.text}")

    def fetch_schedule(self):
        if self.token:
            headers = {"Authorization": self.token}
            response = requests.get(f"{self.server_url}/fetch_schedule", headers=headers)
            if response.status_code == 200:
                logger.info(f"Schedule has been fetched: {response.json()}")
                return response.json()
            else:
                logger.error(f"Failed to fetch schedule: {response.text}")
                return {}