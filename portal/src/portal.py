from flask import Blueprint, render_template, abort, session, jsonify, g
from datetime import datetime, date
from . import utils
import pymongo
import logging
import secrets
import os
import json
import requests

portal = Blueprint("portal", __name__)


@portal.before_request
def before_request():
    from . import db
    g.db = db


@portal.route("/portal", methods=["GET"])
@utils.login_required
def home():
    url_1 = "http://localhost:8000/api/logs/6651862de66ba56c4dd11a9d"
    url_2 = "http://localhost:8000/api/requestCount/6651862de66ba56c4dd11a9d"
    url_3 = "http://localhost:8000/api/analysis"
    
    api_logs = requests.get(url=url_1)
    request_count = requests.get(url=url_2).json()
    api_logs_json = api_logs.json()
    api_analysis = requests.get(url=url_3)
    api_analysis_json = api_analysis.json()
    
    
    for record in api_logs_json:
        record['date'] = datetime.strptime(record['date'], '%a, %d %b %Y %H:%M:%S %Z').date().isoformat()
        record['resp_time'] = round(record['resp_time'], 4)
        record['time'] = record['time'].split('.')[0]
    
    return render_template("index.html", api_logs=api_logs_json, request_count=request_count, api_analysis=api_analysis_json)


@portal.route("/dashboard", methods=["GET"])
@utils.login_required
def dashboard():
    url_1 = "http://localhost:8000/api/logs/6651862de66ba56c4dd11a9d"
    url_2 = "http://localhost:8000/api/requestCount/6651862de66ba56c4dd11a9d"
    
    api_logs = requests.get(url=url_1)
    request_count = requests.get(url=url_2).json()
    api_logs_json = api_logs.json()
    
    for record in api_logs_json:
        record['date'] = datetime.strptime(record['date'], '%a, %d %b %Y %H:%M:%S %Z').date().isoformat()
        record['resp_time'] = round(record['resp_time'], 4)
        record['time'] = record['time'].split('.')[0]
    
    return render_template("partials/dashboard.html", api_logs=api_logs_json, request_count=request_count)


@portal.route("/profile", methods=["GET"])
@utils.login_required
def profile():
    email = session.get("email")
    
    query = {"email": email}
    
    try:
        record = g.db.users.find_one(query)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query User({email}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")

    if not record:
        return jsonify({"message": "Record Not Found!"}), 404
    
    dob = record['dob']

    age = date.today().year - dob.year - \
        ((date.today().month, date.today().day) < (dob.month, dob.day))
        
    user = {
        "username": record['username'],
        "email": email,
        "dob": dob.strftime("%d-%m-%Y"),
        "age": age,
        "gender": record['gender']
    }
    
    return render_template("partials/profile.html", user=user)


@portal.route("/key", methods=["GET"])
@utils.login_required
def get_api_key():
    email = session.get("email")
    api_key = secrets.token_urlsafe(32)
    hashed_key = utils.hash_with_pepper(api_key)
    
    url = f"{os.getenv('HEALTHCARE_SERVICE_URL')}/internal/api/user"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    data = json.dumps(
        {
            'email': email,
            'api_key': hashed_key
        }
    )
    
    requests.put(url=url, data=data, headers=headers)
    utils.send_apikey_email(reciever_email=email, api_key=api_key)
    
    message = "API key sent successfully!"
    return message


@portal.route("/", methods=["DELETE"])
@utils.login_required
def delete_account():
    email = session.get("email")
  
    url = f"{os.getenv('HEALTHCARE_SERVICE_URL')}/internal/api/user?email={email}"
    requests.delete(url=url)
    
    query = {"email": email}
    
    try:
        g.db.users.delete_one(query)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't delete user({email}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    session.clear()

    return jsonify({"message": "Account Deleted Successfully!"}), 200
