from flask import Blueprint, request, abort, jsonify, g
from pydantic import ValidationError
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError
from datetime import datetime, date
from api import utils, schemas
import redis
import time
import json
import threading
import requests
import logging

appointment = Blueprint("appointment", __name__, url_prefix="/api/appointments")

@appointment.before_request
def before_request():
    from api import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)
    g.request_time = time.time()
    g.request_date = date.today()
    

@appointment.after_request
def after_request(response):
    g.status_code = response.status_code
    g.response_time = time.time() - g.request_time
    
    return response


@appointment.teardown_request
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
    
    
@appointment.route("/<app_id>", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_appointment_by_id(app_id):
    user_id = getattr(request, "user_id", None)
    
    if len(app_id) != 24:
        abort(400, "Invalid Appointment ID")
        
    query = {"_id": ObjectId(app_id), "uid": ObjectId(user_id)}
    
    try:
        record = g.db.appointments.find_one(query)
        if not record:
            return jsonify({"message": "Record Not Found!"}), 404
        
    except PyMongoError as e:
        logging.error(f"Couldn't query appointment(id: {app_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    data = {"id": str(record["_id"]), "Patient ID": str(record["patient_id"]),
            "Doctor ID": str(record["doctor_id"]), "Date": record['date'], "status": record['status']}
        
    return jsonify({"Appointment": data}), 200


@appointment.route("/", methods=["GET"], strict_slashes=False)
@utils.api_key_required
def get_appointments_by_pid_or_did():
    user_id = getattr(request, "user_id", None)
    patient_id = request.args.get("patient_id")
    doctor_id = request.args.get("doctor_id")
    page = request.args.get("page") or 1
    offset = (int(page) * 20) - 20
    
    if not patient_id and not doctor_id:
        abort(400, "No ID is provided. Please provide pateint id or doctor id or even both")
        
    if patient_id and not doctor_id:
        if len(patient_id) != 24:
            abort(400, "Invalid Patient ID")
    
        query = {"patient_id": ObjectId(patient_id), "uid": ObjectId(user_id)}
        
    elif doctor_id and not patient_id:
        if len(doctor_id) != 24:
            abort(400, "Invalid Doctor ID")
    
        query = {"doctor_id": ObjectId(doctor_id), "uid": ObjectId(user_id)}
    
    else:
        if len(doctor_id) != 24 or len(patient_id) != 24:
            abort(400, "Invalid ID provided")
            
        query = {"patient_id": ObjectId(patient_id), "doctor_id": ObjectId(doctor_id), "uid": ObjectId(user_id)}
        
    try:
        records = g.db.appointments.find(query).skip(offset).limit(20)
        if not records:
            abort(404, "No Record Found!")
    except PyMongoError as e:
        logging.error(f"Couldn't query appointment record(uid: {user_id}, pid: {patient_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    appointments = [{"ID": str(r['_id']), "Patient ID": str(r['patient_id']), "Doctor ID": str(r['doctor_id']),
                     "Date": r['date'], "Status": r['status']} for r in records]
        
    return jsonify({"Appointments": appointments}), 200


@appointment.route("/", methods=["POST"], strict_slashes=False)
@utils.api_key_required
def book_appointment():
    user_id = getattr(request, "user_id", None)
    
    try:
        schemas.Appointment(**request.json)
    except ValidationError as e:
        abort(400, f"Invalid Request. Error: {e}")
        
    data = request.json
    data['patient_id'] = ObjectId(data['patient_id'])
    data['doctor_id'] = ObjectId(data['doctor_id'])
    data['uid'] = ObjectId(user_id)
    data['date'] = datetime.strptime(data['date'], "%Y-%m-%d")
        
    try:
        g.db.appointments.insert_one(data)
    except PyMongoError as e:
        logging.error(f"Couldn't add appointment record(uid: {user_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    return jsonify({"message": "Appointment added Successfully!"}), 200


@appointment.route("/<app_id>", methods=["PUT"], strict_slashes=False)
@utils.api_key_required
def update_appointment_status(app_id):
    user_id = getattr(request, "user_id", None)
    status = request.args.get("status")
    
    if len(app_id) != 24:
        abort(400, "Invalid Appointment ID")
        
    if status not in ("pending", "done", "cancelled"):
        abort(400, "Invalid status for appointment")
        
    query = {"_id": ObjectId(app_id), "uid": ObjectId(user_id)}
    update = {'$set': {'status': status}}
    
    try:
        exists = g.db.appointments.find_one(query)
        if not exists:
            abort(404, "Record Not Found!")
    except PyMongoError as e:
        logging.error(f"Couldn't query appointment record(app_id: {app_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    try:
        g.db.appointments.update_one(query, update)
    except PyMongoError as e:
        logging.error(f"Couldn't update appointment status(app_id: {app_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    return jsonify({"message": "Successfully updated appointment status"}), 200
    

@appointment.route("/<app_id>", methods=["DELETE"], strict_slashes=False)
@utils.api_key_required
def delete_appointment(app_id):
    user_id = getattr(request, "user_id", None)
    
    if len(app_id) != 24:
        abort(400, "Invalid Appointment ID")
        
    query = {"_id": ObjectId(app_id), "uid": ObjectId(user_id)}
    
    try:
        g.db.appointments.delete_one(query)
    except PyMongoError as e:
        logging.error(f"Couldn't delete appointment({app_id}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    return jsonify({"message": "Record Deleted Successfully!"})
