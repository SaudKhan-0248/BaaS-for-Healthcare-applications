from flask import Blueprint, request, abort, g, jsonify
from pymongo.errors import PyMongoError
from .utils import invalidate_key_cache, delete_related_records
import redis
import logging

internal_api = Blueprint("internal_api", __name__, url_prefix="/internal/api/user")
INTERNAL_IPS = {'localhost', '127.0.0.1'}


@internal_api.before_request
def before_request():
    from . import db, cache_pool
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)


@internal_api.route("/", methods=["PUT"])
def add_or_update_user():
    if request.remote_addr not in INTERNAL_IPS:
        abort(404)
    
    email = request.json.get("email")
    api_key = request.json.get("api_key")
    
    invalidate_key_cache(email=email)
    
    query = {"email": email}
    
    data = {
        '$set': {
            "api_key": api_key
        }
    }
    
    try:
        g.db.users.update_one(query, data, upsert=True)
    except PyMongoError as e:
        logging.error(f"Couldn't Insert User data into Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    return jsonify({"message": "user added in API successfully!"}), 200
    

@internal_api.route("/", methods=["DELETE"])
def delete_user():
    if request.remote_addr not in INTERNAL_IPS:
        abort(404)
        
    email = request.args.get("email")
    
    query = {'email': email}
    
    record = g.db.users.find_one(query)
    user_id = record['_id']
    
    invalidate_key_cache(email=email)
    delete_related_records(user_id=user_id)
    
    try:
        g.db.users.delete_one(query)
    except PyMongoError as e:
        logging.error(f"Couldn't delete User data from Database. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    return jsonify({"message": "Record deleted Successfully!"}), 200
