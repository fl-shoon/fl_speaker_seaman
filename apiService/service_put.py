import requests
from etc.define import *

class PutData:
    def __init__(self, id, url):
        self.token = None
        self.speaker_id = id 
        self.server_url = url
        self.sensor_data_schema = {
            'temperatureSensor': int,
            'irSensor': bool,
            'brightnessSensor': int,  
        }

    def validate_data_types(self, data):
        invalid_fields = []
        for field, value in data.items():
            if field in self.sensor_data_schema:
                if not isinstance(value, self.sensor_data_schema[field]):
                    invalid_fields.append(f"{field} (expected {self.sensor_data_schema[field].__name__}, got {type(value).__name__})")
            else:
                invalid_fields.append(f"{field} (unexpected field)")
        return invalid_fields

    def update_sensor_data(self, token, data):
        invalid_fields = self.validate_data_types(data)
        if invalid_fields: return False
        headers = {"Authorization": token, "uid": self.speaker_id, "Content-Type": "application/json"}
        response = requests.put(f"{self.server_url}/update_sensor_data", headers=headers, json=data)
        if response.status_code == 200:
            response_json = response.json()
            success = response_json['success']
            return success
        else:
            logger.error(f"Failed to update Firestore data: {response.text}")
            return False