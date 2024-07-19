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

ipd_record = Blueprint("ipd_record", __name__, url_prefix="/api/ipd")


@ipd_record.before_request
def before_request():
    from api import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)
    g.request_time = time.time()
    g.request_date = date.today()
    

@ipd_record.after_request
def after_request(response):
    g.status_code = response.status_code
    g.response_time = time.time() - g.request_time
    
    return response


@ipd_record.teardown_request
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


@ipd_record.route("/", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_ipds():
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
        
    ipd_records = list()

    for record in records:
        if not record.get("ipd_records"):
            continue
        ipd_records.append({"patient_id": str(record['_id']),
                            "ipds": [{"ID": r['id'],
                                      "admission": r['admission_date'],
                                      "chief_complaint": r['chief_complaint']} for r in record['ipd_records']]})
        
    return ipd_records, 200


@ipd_record.route("/byDate", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_ipd_by_date():
    user_id = getattr(request, "user_id", None)
    page = request.args.get("page") or 1
    offset = (int(page) * 10) - 10
    date = request.args.get("date")
    
    if not date:
        abort(400, "Date is not Provided")
         
    query = {"uid": ObjectId(user_id), "ipd_records": {"$elemMatch": {"admission_date": date}}}
        
    try:
        records = g.db.patients.find(query).skip(offset).limit(10)
        if not records:
            return jsonify({"message": "Invalid Patient ID"}), 400
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    ipd_records = list()
    
    for record in records:
        if not record.get("ipd_records"):
            continue
        ipd_records.append({"patient_id": str(record['_id']),
                                    "ipds": [{"ID": r['id'],
                                            "admission": r['admission_date'],
                                            "chief_complaint": r['chief_complaint']} for r in record['ipd_records'] if r['admission_date'] == date]})
        
    return jsonify({"IPD records": ipd_records}), 200  
    

@ipd_record.route("/<patient_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_ipd_of_patient(patient_id):
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
        
    if 'ipd_records' not in record.keys():
        return jsonify({"message": "No IPD records found!"}), 404
    
    ipd_records = [{"ID": r['id'], "admission": r['admission_date'],
                    "chief_complaint": r['chief_complaint']} for r in record['ipd_records']]
    
    return jsonify({"IPD records": ipd_records}), 200


@ipd_record.route("/<patient_id>/<ipd_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_ipd_by_id(patient_id, ipd_id):
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
        
    ipd_records = patient['ipd_records']
    
    for record in ipd_records:
        if record['id'] == ipd_id:
            return jsonify({"IPD Record": record})
        
    return jsonify({"message": "No Record Found!"}), 404


@ipd_record.route("/byDate/<patient_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_ipd_of_patient_by_date(patient_id):
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
    
    ipd_records = patient['ipd_records']
    filtered_records = [r for r in ipd_records if r['admission_date'] == date]
        
    if not filtered_records:
        return jsonify({"message": "No IPD records found!"}), 404
        
    return jsonify({"IPD records": filtered_records}), 200
        
        
@ipd_record.route("/<patient_id>", methods=["POST"], strict_slashes=False)
@utils.api_key_required
def add_ipd_record(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
    
    try:
        schemas.IpdRecord(**request.json)
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
            '$push': {'ipd_records': data}
        })
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't insert ipd record into the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record added Successfully!"}), 200


@ipd_record.route("/<patient_id>/<ipd_id>", methods=["DELETE"], strict_slashes=False)
@utils.api_key_required
def delete_ipd_record(patient_id, ipd_id):
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
            '$pull': {'ipd_records': {"id": ipd_id}}
        })
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete ipd record from the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record deleted Successfully!"}), 200
