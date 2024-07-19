from flask import Blueprint, request, g, abort, jsonify
from bson.objectid import ObjectId
from datetime import datetime, date
from api import schemas, utils
from pydantic import ValidationError
import redis
import pymongo.errors
import requests
import threading
import json
import logging
import time

doctor = Blueprint("doctor", __name__, url_prefix="/api/doctors")


@doctor.before_request
def before_request():
    from api import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)
    g.request_time = time.time()
    g.request_date = date.today()
    

@doctor.after_request
def after_request(response):
    g.status_code = response.status_code
    g.response_time = time.time() - g.request_time
    
    return response


@doctor.teardown_request
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
        

@doctor.route("/<doctor_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_doctor(doctor_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(doctor_id) != 24:
        abort(400, "Invalid Doctor ID")

    query = {"_id": ObjectId(doctor_id), "uid": ObjectId(user_id)}
    
    try:
        record = g.db.doctors.find_one(query)
        if not record:
            return jsonify({"message": "Record Not Found!"}), 404
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}, doc_id: {doctor_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    dob = record['dob']
    age = date.today().year - dob.year - \
        ((date.today().month, date.today().day) < (dob.month, dob.day))
    record['age'] = age
    
    data = {key: str(value) for key, value in record.items()}
    
    return data, 200
    
    
@doctor.route("/", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_doctors():
    user_id = getattr(request, 'user_id', None)
    page = request.args.get("page") or 1
    offset = (int(page) * 20) - 20
    
    query = {"uid": ObjectId(user_id)}
    
    try:
        records = g.db.doctors.find(query).skip(offset).limit(20)
        if not records:
            return jsonify({"message": "Record Not Found!"}), 404
        
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query user data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")

    doctors = list()

    for record in records:
        doctors.append({"id": str(record['_id']),
                         "name": record['name'],
                         "contact_no": record['contact_no']})

    return doctors, 200


@doctor.route("/", methods=["POST"], strict_slashes=False)
@utils.api_key_required
def add_doctor():
    user_id = getattr(request, 'user_id', None)
    
    try:
        doctor = schemas.Doctor(**request.json)
    except ValidationError as e:
        abort(400, f"Invalid Request. Error: {e}")
        
    data = request.json
    data['dob'] = datetime.strptime(str(data['dob']), '%Y-%m-%d')
    data['uid'] = ObjectId(user_id)
    
    try:
        g.db.doctors.insert_one(data)
    except pymongo.errors.DuplicateKeyError:
        abort(400, "A doctor record with this contact_no already exists!")
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't insert doctor data into the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    return jsonify({"message": "Doctor has been Added Successfully!",
                    "doctor_name": doctor.name}), 201
    
    
@doctor.route("/<doctor_id>", methods=["PUT"], strict_slashes=False)
@utils.api_key_required
def update_doctor(doctor_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(doctor_id) != 24:
        abort(400, "Invalid Doctor ID")
    
    query = {"_id": ObjectId(doctor_id), "uid": ObjectId(user_id)}
    
    try:
        exists = g.db.doctors.find_one(query)
        if not exists:
            abort(401, "Invalid user_id or doctor_id")
            
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query doctor({doctor_id}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    try:
        schemas.DoctorUpdate(**request.json)
    except ValidationError as e:
        abort(400, f"Invalid Request. Error: {e}")
    
    update_fields = request.json.keys()
    
    update = {
        '$set': {field: request.json[field] for field in update_fields}
    }
    
    try:
        g.db.doctors.update_one({"_id": ObjectId(doctor_id)}, update)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Failed to update doctor({doctor_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record Updated Successfully!",
                    "doctor_id": doctor_id})
    
    
@doctor.route("/<doctor_id>", methods=["DELETE"], strict_slashes=False)
@utils.api_key_required
def delete_doctor(doctor_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(doctor_id) != 24:
        abort(400, "Invalid Doctor ID")
    
    query = {"_id": ObjectId(doctor_id), "uid": ObjectId(user_id)}
    
    try:
        g.db.doctors.delete_one(query)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete doctor({doctor_id}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record Deleted Successfully!"})
