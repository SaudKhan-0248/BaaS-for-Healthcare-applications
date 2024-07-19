from flask import Blueprint, session, request, abort, jsonify, g, render_template
from pydantic import ValidationError
from datetime import datetime
import pymongo
import smtplib
import pymongo
import pymongo.errors
import redis
import logging
from .schema import User
from . import utils

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.before_request
def before_request():
    from . import cache_pool, db
    g.db = db
    g.cache_conn = redis.Redis(connection_pool=cache_pool)


@auth.teardown_request
def teardown_request(exception=None):
    if hasattr(g, "cache_conn"):
        g.cache_conn.close()


@auth.route("/register", methods=["POST"])
def register():
    try:
        user = User(**request.json)
    except ValidationError as err:
        abort(400, f"Invalid Request: {err}")

    verification_code = utils.generate_verification_code()

    data = {
        "username": user.username,
        "password": utils.hash_with_pepper(user.password),
        "dob": user.dob.strftime('%Y-%m-%d'),
        "gender": user.gender,
        "verification code": verification_code
    }

    try:
        g.cache_conn.hmset(user.email, data)
        g.cache_conn.expire(user.email, 300)
    except Exception as err:
        logging.error(
            f"Failed to store Registration Data in Verification Cache. Error: {err}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")

    try:
        utils.send_verification_email(reciever_email=user.email, code=verification_code)
    except smtplib.SMTPException:
        g.cache_conn.delete(user.email)
        abort(
            f"Failed to send Verification email. Please try again.")

    return "Verification Code sent Successfully!", 200


@auth.route("/verify", methods=["GET"])
def verify_email():
    email = request.args.get("email")
    verification_code = request.args.get("code")

    if not email or not verification_code:
        abort(400, "Invalid Request")

    if not g.cache_conn.hgetall(email):
        abort(401, "Verification Failed. Either the email is Invalid or Verification code has expired")

    if str(g.cache_conn.hget(email, "verification code").decode()) == verification_code:
        username = str(g.cache_conn.hget(email, "username").decode())
        password = str(g.cache_conn.hget(email, "password").decode())
        dob = datetime.strptime(
            str(g.cache_conn.hget(email, "dob").decode()), '%Y-%m-%d')
        gender = str(g.cache_conn.hget(email, "gender").decode())
        
        data = {
            "username": username,
            "email": email,
            "password": password,
            "dob": dob,
            "gender": gender
        }
        
        try:
            g.db.users.insert_one(data)    
        except pymongo.errors.DuplicateKeyError:
            g.cache_conn.delete(email)
            abort(400, "An account for this email already exists!")
        except pymongo.errors.PyMongoError as e:
            logging.error(f"Couldn't Insert User data into Database. Error: {e}")
            abort(500, "The server encountered an Internal Error and was unable to complete your request")

        g.cache_conn.delete(email)

        return jsonify({"message": "The account has been registered Successfully!"}), 201

    abort(401, "Verification Failed. Incorrect Verification code")


@auth.route("/login", methods=["GET"])
def login():
    email = request.args.get("email")
    password = request.args.get("password")

    if not email or not password:
        abort(400, "Missing Credentials!")
    
    query = {"email": email, "password": utils.hash_with_pepper(password)}
    
    try:
        exists = g.db.users.find_one(query)
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Couldn't query user({email}) data. Error: {e}")
        abort(500, "The server encountered an Internal Error and was unable to complete your request")

    if not exists:
        abort(401, "Invalid Credenetials!")

    session.permanent = True
    session["email"] = email
    session["logged_in_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({"message": "Logged in Successfully!"}), 200


@auth.route('/logout', methods=["GET"])
@utils.login_required
def logout():
    session.clear()
    return render_template("login.html"), 200
