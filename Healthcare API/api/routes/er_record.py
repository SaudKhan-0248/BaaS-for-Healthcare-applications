from flask import Blueprint, request, abort, jsonify, g
from bson.objectid import ObjectId
from pydantic import ValidationError
from datetime import date
import pymongo.errors
from api import schemas, utils
import pymongo
import logging
import redis
import time
import threading
import requests
import json
import uuid

er_record = Blueprint("er_record", __name__, url_prefix="/api/er")


@er_record.before_request
def before_request():
    from api import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)
    g.request_time = time.time()
    g.request_date = date.today()
    

@er_record.after_request
def after_request(response):
    g.status_code = response.status_code
    g.response_time = time.time() - g.request_time
    
    return response


@er_record.teardown_request
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


@er_record.route("/", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_err():
    user_id = getattr(request, "user_id", None)
    page = request.args.get("page") or 1
    offset = (int(page) * 10) - 10
    
    query = {"uid": ObjectId(user_id)}
    
    try:
        records = g.db.patients.find(query).skip(offset).limit(10)
        if not records:
            return jsonify({"message": "Record Not Found!"}), 404
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query user data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    er_records = list()

    for record in records:
        if not record.get("er_records"):
            continue
        er_records.append({"patient_id": str(record['_id']),
                            "err": [{"ID": r['id'],
                                      "date": r['date'],
                                      "chief_complaint": r['chief_complaint']} for r in record['er_records']]})
        
    return er_records, 200


@er_record.route("/byDate", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_err_by_date():
    user_id = getattr(request, "user_id", None)
    page = request.args.get("page") or 1
    offset = (int(page) * 10) - 10
    date = request.args.get("date")
    
    if not date:
        abort(400, "Date is not Provided")
         
    query = {"uid": ObjectId(user_id), "er_records": {"$elemMatch": {"date": date}}}
        
    try:
        records = g.db.patients.find(query).skip(offset).limit(10)
        if not records:
            return jsonify({"message": "Invalid Patient ID"}), 400
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    er_records = list()
    
    for record in records:
        if not record.get("er_records"):
            continue
        er_records.append({"patient_id": str(record['_id']),
                                    "err": [{"ID": r['id'],
                                            "date": r['date'],
                                            "chief_complaint": r['chief_complaint']} for r in record['er_records'] if r['date'] == date]})
        
    return jsonify({"ER records": er_records}), 200  
    

@er_record.route("/<patient_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_err_of_patient(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
        
    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        record = g.db.patients.find_one(query)
        if not record:
            return jsonify({"message": "Invalid Pateint ID"}), 400
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}, pid: {patient_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    if 'er_records' not in record.keys():
        return jsonify({"message": "No ER records found!"}), 404
    
    er_records = [{"ID": r['id'], "date": r['date'],
                    "chief_complaint": r['chief_complaint']} for r in record['er_records']]
    
    return jsonify({"ER records": er_records}), 200


@er_record.route("/<patient_id>/<er_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_err_by_id(patient_id, er_id):
    user_id = getattr(request, "user_id", None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
        
    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        patient = g.db.patients.find_one(query)
        if not patient:
            return jsonify({"message": "Invalid Patient ID"}), 400
        
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}, pid: {patient_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    er_records = patient['er_records']
    
    for record in er_records:
        if record['id'] == er_id:
            return jsonify({"ER Record": record})
        
    return jsonify({"message": "No Record Found!"}), 404


@er_record.route("/byDate/<patient_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_err_of_patient_by_date(patient_id):
    user_id = getattr(request, 'user_id', None)
    date = request.args.get('date')
    
    if not date:
        abort(400, "Date is not provided")
    
    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        patient = g.db.patients.find_one(query)
        if not patient:
            return jsonify({"message": "Invalid Patient ID"}), 400
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}, pid: {patient_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    er_records = patient['er_records']
    filtered_records = [r for r in er_records if r['date'] == date]
        
    if not filtered_records:
        return jsonify({"message": "No ER records found!"}), 404
        
    return jsonify({"ER records": filtered_records}), 200
        
        
@er_record.route("/<patient_id>", methods=["POST"], strict_slashes=False)
@utils.api_key_required
def add_er_record(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
    
    try:
        schemas.ErRecord(**request.json)
    except ValidationError as e:
        abort(400, f"Invalid Request. Error: {e}")
        
    query = {"_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
    
    try:
        exists = g.db.patients.find_one(query)
        if not exists:
            abort(401, "Invalid user_id or patient_id")
            
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query patient({patient_id}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    data = request.json
    data['id'] = str(uuid.uuid4())
    
    try:
        g.db.patients.update_one(query, {
            '$push': {'er_records': data}
        })
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't insert er record into the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record added Successfully!"}), 200


@er_record.route("/<patient_id>/<er_id>", methods=["DELETE"], strict_slashes=False)
@utils.api_key_required
def delete_er_record(patient_id, er_id):
    user_id = getattr(request, "user_id", None)
    
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
        g.db.patients.update_one(query, {
            '$pull': {'er_records': {"id": er_id}}
        })
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete er record from the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record deleted Successfully!"}), 200
