from flask import Blueprint, request, g, abort, jsonify
from pydantic import ValidationError
from bson.objectid import ObjectId
from api import schemas, utils
from datetime import datetime, date
import pymongo.errors
import threading
import redis
import requests
import json
import logging
import time

patient = Blueprint("patient", __name__, url_prefix="/api/patients")


@patient.before_request
def before_request():
    from api import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)
    g.request_time = time.time()
    g.request_date = date.today()

@patient.after_request
def after_request(response):
    g.status_code = response.status_code
    g.response_time = time.time() - g.request_time
    
    return response


@patient.teardown_request
def teardown_request(exception=None):
    if hasattr(g, "cache_conn"):
        g.cache_conn.close()  
        
    url = "http://localhost:8000/api/logs"
    
    headers = {
        'Content-Type': 'application/json'
    }

    data = json.dumps(utils.get_request_data(exception=exception), default=str)
    
    thread = threading.Thread(target=requests.post, kwargs={'url': url, 'data': data, 'headers': headers})
    thread.start()


@patient.route("/<patient_id>", methods=["GET"])
@utils.api_key_required
def get_patient(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")

    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        record = g.db.patients.find_one(query)
        if not record:
            return jsonify({"message": "Record Not Found!"}), 404
        
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}, pid: {patient_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    dob = record['dob']

    age = date.today().year - dob.year - \
        ((date.today().month, date.today().day) < (dob.month, dob.day))
    record['age'] = age
    
    data = {key: str(value) for key, value in record.items() if key not in ('opd_records', 'ipd_records',
                                                                            'er_records')}
    
    return data, 200


@patient.route("/", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_patients():
    user_id = getattr(request, 'user_id', None)
    page = request.args.get("page") or 1
    offset = (int(page) * 20) - 20
    
    query = {"uid": ObjectId(user_id)}
    
    try:
        records = g.db.patients.find(query).skip(offset).limit(20)
        if not records:
            return jsonify({"message": "Record Not Found!"}), 404
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query user data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")

    patients = list()

    for record in records:
        patients.append({"id": str(record['_id']),
                         "name": f"{record['firstname']} {record['lastname']}",
                         "contact_no": record['contact_no']})

    return patients, 200


@patient.route("/", methods=["POST"], strict_slashes=False)
@utils.api_key_required
def add_patient():
    user_id = getattr(request, 'user_id', None)
    
    try:
        patient = schemas.Patient(**request.json)
    except ValidationError as e:
        abort(400, f"Invalid Request. Error: {e}")
        
    data = request.json
    data['dob'] = datetime.strptime(str(data['dob']), '%Y-%m-%d')
    data['uid'] = ObjectId(user_id)
    
    try:
        g.db.patients.insert_one(data)
    except pymongo.errors.DuplicateKeyError:
        abort(400, "A patient record with this contact_no already exists!")
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't insert patient data into the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    return jsonify({"message": "Patient has been Added Successfully!",
                    "patient_name": f"{patient.firstname} {patient.lastname}"}), 201


@patient.route("/<patient_id>", methods=["PUT"], strict_slashes=False)
@utils.api_key_required
def update_patient(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
    
    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        exists = g.db.patients.find_one(query)
        if not exists:
            abort(401, "Invalid user_id or patient_id")
            
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query patient({patient_id}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    try:
        schemas.PatientUpdate(**request.json)
    except ValidationError as e:
        abort(400, f"Invalid Request. Error: {e}")
    
    update_fields = request.json.keys()
    
    update = {
        '$set': {field: request.json[field] for field in update_fields}
    }
    
    try:
        g.db.patients.update_one({"_id": ObjectId(patient_id)}, update)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Failed to update patient({patient_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record Updated Successfully!",
                    "patient_id": patient_id})
    
    
@patient.route("/<patient_id>", methods=["DELETE"], strict_slashes=False)
@utils.api_key_required
def delete_patient(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
    
    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        g.db.patients.delete_one(query)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete patient({patient_id}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record Deleted Successfully!"})
