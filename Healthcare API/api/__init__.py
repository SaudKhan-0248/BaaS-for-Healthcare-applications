from flask import Flask, abort
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
from .routes import patient, doctor, opd_record, ipd_record, er_record, appointment, diagnosis_model
from .internal_api import internal_api
from .utils import schedule_appointment_checks
import threading
import redis
import logging
import os

server = Flask(__name__)
CORS(server, resources={r"/api/*": {"origins": "*"}})
server.secret_key = os.getenv("SECRET_KEY")

logging.getLogger('werkzeug').disabled = True
logging.basicConfig(filename="api.log", level=logging.ERROR,
                    filemode="a", format="%(asctime)s : %(levelname)s : %(message)s")

load_dotenv()

mongo_client = MongoClient(f'mongodb://{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/', maxPoolSize=10)
db = mongo_client[os.getenv("DB_NAME")]
users = db.users
patients = db.patients
doctors = db.doctors
users.create_index("email", unique=True)
patients.create_index([('uid', ASCENDING), ('contact_no', ASCENDING)], unique=True)
doctors.create_index([('uid', ASCENDING), ('contact_no', ASCENDING)], unique=True)

cache_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST"),
            port=os.getenv("REDIS_PORT"),
            db=1,
            max_connections=5
        )

if db == None:
    logging.critical("Couldn't Connect to Database!")
    abort(500, "The server encountered an Internal Error and was unable to complete your request")

if not cache_pool:
    logging.critical("Couldn't Connect to Redis!")
    abort(500, "The server encountered an Internal Error and was unable to complete your request")

server.register_blueprint(patient.patient)
server.register_blueprint(doctor.doctor)
server.register_blueprint(opd_record.opd_record)
server.register_blueprint(ipd_record.ipd_record)
server.register_blueprint(er_record.er_record)
server.register_blueprint(appointment.appointment)
server.register_blueprint(diagnosis_model.model)
server.register_blueprint(internal_api)

appointment_check_thread = threading.Thread(target=schedule_appointment_checks, kwargs={'db': db})
appointment_check_thread.start()
