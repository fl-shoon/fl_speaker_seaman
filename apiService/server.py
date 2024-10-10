from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore
import os

app = Flask(__name__)

cred = credentials.Certificate("../secrets/firebase_admin.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

DEVICE_SCHEMA = {
    'temperatureSensor': int,
    'irSensor': bool,
    'brightnessSensor': int,  
}

def validate_data_types(data):
    invalid_fields = []
    for field, value in data.items():
        if field in DEVICE_SCHEMA:
            if not isinstance(value, DEVICE_SCHEMA[field]):
                invalid_fields.append(f"{field} (expected {DEVICE_SCHEMA[field].__name__}, got {type(value).__name__})")
        else:
            invalid_fields.append(f"{field} (unexpected field)")
    return invalid_fields

@app.route('/fetch_auth_token', methods=['POST'])
def get_token():
    uid = request.headers.get('uid')
    if not uid:
        return jsonify({"error": "Speaker ID is required"}), 400
    
    doc_ref = db.collection('speakers').document(uid)
    doc = doc_ref.get()
    if doc.exists:
        try:
            custom_token = auth.create_custom_token(uid)
            return jsonify({"token": custom_token.decode()})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Speaker not found"}), 404

@app.route('/fetch_schedule', methods=['GET'])
def get_firestore_data():
    id_token = request.headers.get('Authorization')
    if not id_token:
        return jsonify({"error": "No token provided"}), 401

    try:
        doc_ref = db.collection('schedulers').document('medicine_reminder_time')
        doc = doc_ref.get()
        if doc.exists:
            return jsonify(doc.to_dict())
        else:
            return jsonify({"error": "Document not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route('/register_firestore', methods=['POST'])
def register_firestore():
    id_token = request.headers.get('Authorization')
    if not id_token:
        return jsonify({"error": "No token provided"}), 401

    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']

        data = request.json
        doc_ref = db.collection('devices').document(uid)
        doc_ref.set(data, merge=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route('/update_sensor_data', methods=['PUT'])
def update_firestore():
    id_token = request.headers.get('Authorization')
    uid = request.headers.get('uid')
    if not id_token:
        return jsonify({"error": "No token provided"}), 401
    
    if not uid:
        return jsonify({"error": "No speaker id provided"}), 401

    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        invalid_fields = validate_data_types(data)
        if invalid_fields:
            return jsonify({"error": "Invalid data types", "invalid_fields": invalid_fields}), 400

        doc_ref = db.collection('speakers').document(uid)

        doc = doc_ref.get()
        if doc.exists:
            doc_ref.update(data)
            message = "Document updated successfully"
        else:
            doc_ref.set(data)
            message = "Document created successfully"

        return jsonify({"success": True, "message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))