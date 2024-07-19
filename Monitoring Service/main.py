from flask import Flask, jsonify, request, abort, g, Response, stream_with_context
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import psycopg2.pool
import threading
import os
import json

load_dotenv()

service = Flask(__name__)
CORS(service)
service.secret_key = os.getenv("SECRET_KEY")

try:
    pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
        )

except psycopg2.Error:
    abort(500, "The server encountered an Internal Error and was unable to complete your request")
    
    
@service.before_request
def before_request():
    g.conn = pool.getconn()
    

@service.teardown_request
def teardown_request(exception=None):
    if hasattr(g, "conn"):
        pool.putconn(g.conn)
 
        
log_event = threading.Event()


def get_req_count(user_id):
    query = "SELECT total_req, success_resp, error_resp FROM request_count WHERE user_id = %s"
    
    cursor = g.conn.cursor()
    
    cursor.execute(query, (user_id,))
    
    result = cursor.fetchone()
    
    return {'total_req': result[0],
            'success_resp': result[1],
            'error_resp': result[2]}
    

@service.route("/api/logs", methods=["POST"])
def add_api_logs():
    user_id = request.json['user_id']
    req = request.json['request']
    resp = request.json['response']
    
    date = datetime.strptime(req['date'], "%Y-%m-%d")
    time = datetime.fromtimestamp(req['time']).time()
    
    query = """
        INSERT INTO api_logs(user_id, method, endpoint, path, status_code, date, time, resp_time, client_ip)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (user_id,
              req['method'],
              req['endpoint'],
              req['path'],
              resp['status_code'],
              date,
              time,
              resp['response_time'],
              req['client_ip'])
    
    query_additional = """
        INSERT INTO request_count(user_id, total_req, success_resp, error_resp)
        VALUES (%s, 1, %s, %s)
        ON CONFLICT (user_id) DO UPDATE 
        SET total_req = request_count.total_req + 1,
            success_resp = request_count.success_resp + EXCLUDED.success_resp,
            error_resp = request_count.error_resp + EXCLUDED.error_resp
    """
    
    if resp['status_code'] >= 200 and resp['status_code'] < 400:
        success_increment = 1
        failure_increment = 0
    else:
        success_increment = 0
        failure_increment = 1
        
    params_additional = (user_id, success_increment, failure_increment)
    
    cursor = g.conn.cursor()
    
    try:
        cursor.execute(query, params)
        cursor.execute(query_additional, params_additional)
        g.conn.commit()
    except psycopg2.errors.Error:
        g.conn.rollback()
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    log_event.set()
    
    return jsonify({"message": "Log added Successfully"}), 200
    
    
@service.route("/api/logs/<user_id>", methods=["GET"])
def get_api_logs(user_id):    
    query = "SELECT method, path, status_code, date, time, resp_time, client_ip FROM api_logs WHERE user_id = %s ORDER BY date DESC, time DESC LIMIT 7"
    
    cursor = g.conn.cursor()
    
    try:
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
    except psycopg2.errors.Error:
        g.conn.rollback()
        abort(500, "The server encountered an Internal Error and was unable to complete your request")
        
    cursor.close()
    
    if not rows:
        return "Record Not Found!", 404
    
    data = [{"method": row[0],
             "path": row[1],
             "status_code": row[2],
             "date": row[3],
             "time": str(row[4]),
             "resp_time": row[5],
             "client_ip": row[6]} for row in rows]
    
    return jsonify(data), 200


@service.route("/api/requestCount/<user_id>", methods=["GET"])
def get_request_count(user_id):
    result = get_req_count(user_id=user_id)
    
    return result, 200


@service.route("/api/analysis", methods=["GET"])
def api_analysis():
    avg_resp_query = "SELECT AVG(resp_time) FROM api_logs;"
    peak_hours_query = "SELECT EXTRACT(hour FROM time) AS hour, COUNT(*) FROM api_logs GROUP BY hour ORDER BY COUNT(*) DESC LIMIT 1;"
    top_endpoint_query = "SELECT endpoint, COUNT(*) AS request_count FROM api_logs GROUP BY endpoint ORDER BY request_count DESC LIMIT 1;"
    
    cursor = g.conn.cursor()
    
    cursor.execute(avg_resp_query)
    avg_response_time = cursor.fetchone()[0]
    avg_response_time = round(avg_response_time, 3)
    
    cursor.execute(peak_hours_query)
    peak_hour_data = cursor.fetchone()
    
    cursor.execute(top_endpoint_query)
    top_endpoint_data = cursor.fetchall()
    
    return jsonify({"average_response_time": avg_response_time,
                    "peak_hour": f"{peak_hour_data[0]}:00",
                    "requests_in_peak_hour": peak_hour_data[1],
                    "top_endpoint": top_endpoint_data[0][0],
                    "requests_to_top_endpoint": top_endpoint_data[0][1]})


@service.route("/stream/<user_id>")
def stream(user_id):
    def event_stream():
        while True:
            print("waiting for event")
            log_event.wait()
            log_event.clear()
            print("event happend")
            
            result = get_req_count(user_id=user_id)
            data = json.dumps(result)
            
            print(data)
            
            yield f"data: {data}\n\n"
            
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")


if __name__ == "__main__":
    service.run(debug=True, port=8000)
    