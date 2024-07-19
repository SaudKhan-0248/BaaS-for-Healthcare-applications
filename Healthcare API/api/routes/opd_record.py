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

opd_record = Blueprint("opd_record", __name__, url_prefix="/api/opd")


@opd_record.before_request
def before_request():
    from api import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)
    g.request_time = time.time()
    g.request_date = date.today()
    

@opd_record.after_request
def after_request(response):
    g.status_code = response.status_code
    g.response_time = time.time() - g.request_time
    
    return response


@opd_record.teardown_request
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


@opd_record.route("/", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_opds():
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
        
    opd_records = list()

    for record in records:
        if not record.get("opd_records"):
            continue
        opd_records.append({"patient_id": str(record['_id']),
                            "opds": [{"ID": r['id'],
                                      "doctor": r['doctor'],
                                      "date": r['date']} for r in record['opd_records']]})
        
    return opd_records, 200


@opd_record.route("/byDate", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_opd_by_date():
    user_id = getattr(request, "user_id", None)
    page = request.args.get("page") or 1
    offset = (int(page) * 10) - 10
    date = request.args.get("date")
    
    if not date:
        abort(400, "Date is not Provided")
         
    query = {"uid": ObjectId(user_id), "opd_records": {"$elemMatch": {"date": date}}}
        
    try:
        records = g.db.patients.find(query).skip(offset).limit(10)
        if not records:
            return jsonify({"message": "Invalid Patient ID"}), 400
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query record(uid: {user_id}. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    opd_records = list()
    
    for record in records:
        if not record.get("opd_records"):
            continue
        opd_records.append({"patient_id": str(record['_id']),
                                    "opds": [{"ID": r['id'],
                                            "doctor": r['doctor'],
                                            "date": r['date']} for r in record['opd_records'] if r['date'] == date]})
        
    return jsonify({"OPD records": opd_records}), 200  
    

@opd_record.route("/<patient_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_all_opd_of_patient(patient_id):
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
        
    if 'opd_records' not in record.keys():
        return jsonify({"message": "No OPD records found!"}), 404
    
    opd_records = [{"ID": r['id'], "doctor": r['doctor'], "date": r['date']} for r in  record['opd_records']]
    
    return jsonify({"OPD records": opd_records}), 200


@opd_record.route("/<patient_id>/<opd_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_opd_by_id(patient_id, opd_id):
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
        
    opd_records = patient['opd_records']
    
    for record in opd_records:
        if record['id'] == opd_id:
            return jsonify({"OPD Record": record})
        
    return jsonify({"message": "No Record Found!"}), 404


@opd_record.route("/byDate/<patient_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_opd_of_patient_by_date(patient_id):
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
    
    opd_records = patient['opd_records']
    filtered_records = [r for r in opd_records if r['date'] == date]
        
    if not filtered_records:
        return jsonify({"message": "No OPD records found!"}), 404
        
    return jsonify({"OPD records": filtered_records}), 200
        
        
@opd_record.route("/<patient_id>", methods=["POST"], strict_slashes=False)
@utils.api_key_required
def add_opd_record(patient_id):
    user_id = getattr(request, 'user_id', None)
    
    if len(patient_id) != 24:
        abort(400, "Invalid Patient ID")
    
    try:
        schemas.OpdRecord(**request.json)
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
            '$push': {'opd_records': data}
        })
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't insert opd record into the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record added Successfully!"}), 200


@opd_record.route("/<patient_id>/<opd_id>", methods=["DELETE"], strict_slashes=False)
@utils.api_key_required
def delete_opd_record(patient_id, opd_id):
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
            '$pull': {'opd_records': {"id": opd_id}}
        })
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete opd record from the Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record Deleted Successfully!"}), 200
