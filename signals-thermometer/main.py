"""
Accesses the data in Firebase Realtime Database from a certain wireless thermometer and uploads to InfluxDB.
"""

import pprint
from influxdb import InfluxDBClient
import requests


def upload_data(host, port, user, password, dbname, data):
    print('Uploading this data:\n')
    pprint.pprint(data)
    client = InfluxDBClient(host, port, user, password, dbname, ssl=True, verify_ssl=False)
    return client.write_points(data, time_precision='s')


# Log in and return the idToken that needs to be used in future requests.
def log_in(api_key, email, password):
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}'
    headers = {'Content-Type': 'application/json'}
    data = {'email': email, 'password': password, 'returnSecureToken': 'true'}

    print("Requesting: " + url)
    print("Headers: ")
    pprint.pprint(headers)
    print("Data: ")
    pprint.pprint(data)
    response = requests.post(url, json=data, headers=headers)
    if response:
        return response.json()['idToken']
    else:
        return None


# Get the names of the sensors to use in the graph.
def get_names(device_id, id_token):
    url = f'https://smoke-cloud.firebaseio.com/signals/{device_id}/names.json?print=pretty&auth={id_token}'

    response = requests.get(url)
    if response:
        return response.json()
    else:
        return None


# Get the temperatures
def get_temps(device_id, id_token, limit):
    url = f'https://smoke-cloud.firebaseio.com/SignalTemps/{device_id}/.json?orderBy="$key"&limitToLast={limit}&print=pretty&auth={id_token}'

    response = requests.get(url)
    if response:
        return response.json()
    else:
        return None


def transform_point(probe, device_id, device_name, probe_names, value):
    if value[probe] != '---':
        return {
            'measurement': 'environment_sensor',
            'tags': {
                'sensor_id': device_name + '-' + probe_names[probe],
                'original_sensor_id': device_id + '-' + probe,

            },
            'time': int(value['time']),
            'fields': {
                'temperature': float(value[probe])
            }
        }
    return None


def transform_points(device_id, device_name, probe_names, temps):
    points = []
    for key, value in temps.items():
        p = transform_point('p1', device_id, device_name, probe_names, value)
        if p:
            points.append(p)
        p = transform_point('p2', device_id, device_name, probe_names, value)
        if p:
            points.append(p)
        p = transform_point('p3', device_id, device_name, probe_names, value)
        if p:
            points.append(p)
        p = transform_point('p4', device_id, device_name, probe_names, value)
        if p:
            points.append(p)
    return points


def process_data(email, password, device_id, device_name, api_key,
                 influx_host, influx_port, influx_user, influx_password, influx_dbname):
    # Log in
    id_token = log_in(api_key, email, password)
    print('Id Token: ')
    pprint.pprint(id_token)

    # Get the names of the devices
    names = get_names(device_id, id_token)
    print('Names: ')
    pprint.pprint(names)

    # Get the most recent temperatures
    temps = get_temps(device_id, id_token, 50)  # 6 (10 sec) * 5 minutes = 30 (50 just to be safe).
    # print('Temps: ')
    # pprint.pprint(temps)

    # Convert to InfluxDB format.
    points = transform_points(device_id, device_name, names, temps)

    if upload_data(influx_host, influx_port, influx_user, influx_password, influx_dbname, points):
        return f'Success!\n'
    else:
        return f'Failed :(\n'


def upload_function(request):
    email = request.args.get('email', None)
    password = request.args.get('password', None)
    device_id = request.args.get('device_id', None)
    device_name = request.args.get('device_name', None)

    api_key = request.environ.get("api_key")
    influx_host = request.environ.get("influxdb_host")
    influx_port = request.environ.get("influxdb_port")
    influx_user = request.environ.get("influxdb_user")
    influx_password = request.environ.get("influxdb_password")
    influx_dbname = request.environ.get("influxdb_database")

    return process_data(email, password, device_id, device_name, api_key,
                        influx_host, influx_port, influx_user, influx_password, influx_dbname)


# Debug server that can be called directly.
if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        return upload_function(request)

    app.run('127.0.0.1', 8000, debug=True)

