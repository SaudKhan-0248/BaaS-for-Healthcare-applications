from flask import request, abort, g
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from datetime import datetime
from api import utils
import pymongo
import logging
import hashlib
import os
import time
import schedule

import pymongo.errors

load_dotenv()


def hash_with_pepper(credentials: str):
    peppered_cred = credentials + os.getenv("PEPPER")

    hashed_cred = hashlib.sha256(peppered_cred.encode()).hexdigest()
    return hashed_cred


def api_key_required(func):
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("Authorization")

        if not api_key:
            abort(401, "API Key is Missing!")

        hashed_key = utils.hash_with_pepper(api_key)

        if g.cache_conn.exists(hashed_key):
            user_id = g.cache_conn.get(hashed_key).decode('utf-8')
            setattr(request, 'user_id', user_id)

        else:
            query = {"api_key": hashed_key}
            
            try:
                record = g.db.users.find_one(query)
            except pymongo.errors.PyMongoError as e:
                logging.error(f"Couldn't query user data. Error: {e}")
                abort(500, "The server encountered an Internal Error and was unable to complete your request")

            if not record:
                abort(401, "Invalid API Key!")
                
            user_id = str(record.get('_id'))
            
            setattr(request, 'user_id', user_id)
            
            g.cache_conn.set(hashed_key, user_id, ex=3600)

        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def get_request_data(exception):
    user_id = getattr(request, 'user_id', None)
    
    if not user_id:
        return
    
    request_data = {
        "endpoint": request.endpoint,
        "method": request.method,
        "path": request.path,
        "client_ip": request.remote_addr,
        "date": g.request_date,
        "time": g.request_time
    }
    
    if not exception:
        data = {
            "user_id": user_id,
            "request": request_data,
            "response": {
                "response_time": str(g.response_time),
                "status_code": g.status_code
            }
        }    
        
    else:
        status_code = 500
        if isinstance(exception, HTTPException):
            status_code = exception.code
            
        data = {
            "user_id": user_id,
            "request": request_data,
            "response": {
                "status_code": status_code
            }
        }
        
    return data


def invalidate_key_cache(email):
    query = {"email": email}
    
    record = g.db.users.find_one(query)
    
    if not record:
        return
    
    key = record.get('api_key')

    if key:
        if g.cache_conn.exists(key):
            g.cache_conn.delete(key)


def delete_related_records(user_id: str):
    try:
        with g.db.client.start_session() as session:
            with session.start_transaction():
                g.db.patients.delete_many({"uid": user_id})
                g.db.doctors.delete_many({"uid": user_id})
                g.db.appointments.delete_many({"uid": user_id})
                session.commit_transaction()
                
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete records related to user({user_id}). Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")


def check_and_update_appointments(db):
    current_date = datetime.now().date()
    query = {"date": {"$lt": datetime.combine(current_date, datetime.min.time())}, "status": "pending"}
    update = {"$set": {"status": "cancelled"}}
    
    print("Checking appointments!")
    try:
        db.appointments.update_many(query, update)
    except pymongo.errors.CollectionInvalid:
        print("Collection does not exist. Waiting for the next scheduled check.")
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't update Appointment status. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")


def schedule_appointment_checks(db):
    schedule.every().hour.do(lambda: check_and_update_appointments(db=db))
    
    while True:
        schedule.run_pending()
        time.sleep(1)
        