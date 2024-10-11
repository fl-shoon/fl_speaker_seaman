import requests
from etc.define import *

class PutData:
    def __init__(self):
        self.token = None
        self.speaker_id = SPEAKER_ID 
        self.server_url = SERVER_URL
        self.sensor_data_schema = {
            'temperatureSensor': str,
            'irSensor': bool,
            'brightnessSensor': str,  
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
        if invalid_fields: return 
        headers = {"Authorization": token, "uid": self.speaker_id, "Content-Type": "application/json"}
        response = requests.put(f"{self.server_url}/update_sensor_data", headers=headers, json=data)
        if response.status_code == 200:
            response_json = response.json()
            success = response_json['success']
            logger.info(f"Success : {success} : Updated sensor data successfully: {response.text}")
        else:
            logger.error(f"Failed to update sensor data: {response.text}")