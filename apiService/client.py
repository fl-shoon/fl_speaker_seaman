import requests

SERVER_URL = "http://127.0.0.1:8080/"  
DEVICE_ID = "CUXMYPcasUzPF11IaNSe"  

def get_custom_token():
    headers = {"uid": DEVICE_ID}
    response = requests.post(f"{SERVER_URL}/get_token", headers=headers)
    if response.status_code == 200:
        return response.json()['token']
    else:
        raise Exception(f"Failed to get token: {response.text}")

def get_firestore_data(id_token):
    headers = {"Authorization": id_token}
    response = requests.get(f"{SERVER_URL}/get_firestore_data", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get Firestore data: {response.text}")

def update_firestore_data(id_token, uid, data):
    headers = {"Authorization": id_token, "uid": uid, "Content-Type": "application/json"}
    response = requests.put(f"{SERVER_URL}/update_firestore", headers=headers, json=data)
    if response.status_code == 200:
        return response.json(), response.status_code
    else:
        raise Exception(f"Failed to update Firestore data: {response.text}")

def main():
    try:
        id_token = get_custom_token()
        print(id_token)
        
        # Get Firestore data
        firestore_data = get_firestore_data(id_token)
        print("Firestore data:", firestore_data)
        
        # Update Firestore data
        new_data = {"irSensor": False, "temperatureSensor": 70}
        update_result, status_code = update_firestore_data(id_token, DEVICE_ID, new_data)
        print("Status code:", status_code)
        print("Update result:", update_result)
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()