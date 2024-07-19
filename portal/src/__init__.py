from flask import Flask, abort
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import timedelta
from flask_swagger_ui import get_swaggerui_blueprint
from .auth import auth
from .portal import portal
import redis
import logging
import os

load_dotenv()

server = Flask(__name__)
CORS(server)
server.secret_key = os.getenv("SECRET_KEY")
server.permanent_session_lifetime = timedelta(days=1)
SWAGGER_URL = '/api/docs'
API_URL = '/static/openapi.yml'

logging.getLogger('werkzeug').disabled = True
logging.basicConfig(filename="auth.log", level=logging.ERROR,
                    filemode="a", format="%(asctime)s : %(levelname)s : %(message)s")

mongo_client = MongoClient(f'mongodb://{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/', maxPoolSize=10)
db = mongo_client[os.getenv("DB_NAME")]
users = db.users
users.create_index("email", unique=True)

cache_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST"),
            port=os.getenv("REDIS_PORT"),
            db=0,
            max_connections=5
        )

if db == None:
    logging.critical("Couldn't Connect to Database!")
    abort(500, "The server encountered an Internal Error and was unable to complete your request")

if not cache_pool:
    logging.critical("Couldn't Connect to Redis!")
    abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Notes API"
    }
)

server.register_blueprint(auth)
server.register_blueprint(portal)
server.register_blueprint(swaggerui_blueprint)
