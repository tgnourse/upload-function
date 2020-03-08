"""
API requests are capped at 1 request/second for each user's apiKey and 3 requests/second per applicationKey.
When this limit is exceeded, the API will return a 429 response code. Please be kind to our servers :)
"""

import pprint
from influxdb import InfluxDBClient
import requests
import json


def get_devices(application_key, api_key):
    url = f'https://api.ambientweather.net/v1/devices/?apiKey={api_key}&applicationKey={application_key}&limit=1'

    response = requests.get(url)
    if response:
        return response.json()
    else:
        return None


def vapor_density(temperature, humidity):
    temp_c = (temperature - 32) * (5.0/9.0)
    saturation_vapor_density = 5.018+0.32321*temp_c+8.1847*0.0081847*temp_c*temp_c+0.00031243*temp_c*temp_c*temp_c
    return (humidity / 100.0) * saturation_vapor_density


def transform_outdoor(mac, location, name, sensor_name, station_data):
    if station_data.get('tempf'):
        return [
            {
                "measurement": "environment_sensor",
                "tags": {
                    "sensor_id": sensor_name + "_outdoor",
                    "original_sensor_id": mac + "_outdoor",
                    "location": location,
                    "name": name,
                    "mac": mac,
                    "outdoor": True
                },
                "time": station_data.get('date'),
                "fields": {
                    "temperature": float(station_data.get('tempf')),
                    "humidity": float(station_data.get('humidity')),
                    "vapor_density": vapor_density(station_data.get('tempf'), station_data.get('humidity')),
                    "solar_radiation": float(station_data.get('solarradiation')),
                    "wind_direction": station_data.get('winddir'),
                    "wind_speed_mph": float(station_data.get('windspeedmph')),
                    "wind_speed_max_10min_mph": float(station_data.get('windgustmph')),
                    "wind_speed_max_daily_mph": float(station_data.get('maxdailygust')),
                    "uv": float(station_data.get('uv')),
                    "hourly_rain_inches": float(station_data.get('hourlyrainin')),
                    "daily_rain_inches": float(station_data.get('dailyrainin')),
                    "weekly_rain_inches": float(station_data.get('weeklyrainin')),
                    "monthly_rain_inches": float(station_data.get('monthlyrainin')),
                    "battery_status": float(station_data.get('battout', -1))
                }
            }
        ]
    return None


def transform_indoor(mac, location, name, sensor_name, station_data):
    pressure = None
    if station_data.get('baromabsin'):
        pressure = float(station_data.get('baromabsin', 0))
    return [
        {
            "measurement": "environment_sensor",
            "tags": {
                "sensor_id": sensor_name + "_indoor",
                "original_sensor_id": mac + "_indoor",
                "location": location,
                "name": name,
                "mac": mac,
                "indoor": True
            },
            "time": station_data.get('date'),
            "fields": {
                "temperature": float(station_data.get('tempinf')),
                "humidity": float(station_data.get('humidityin')),
                "vapor_density": vapor_density(station_data.get('tempinf'), station_data.get('humidityin')),
                "pressure": pressure,
            }
        }
    ]


def transform_num(mac, location, name, sensor_name, station_data, num):
    temp_key = 'temp' + str(num) + 'f'
    hum_key = 'humidity' + str(num)

    if station_data.get(temp_key):
        return [
            {
                "measurement": "environment_sensor",
                "tags": {
                    "sensor_id": sensor_name + "_" + str(num),
                    "original_sensor_id": mac + "_" + str(num),
                    "location": location,
                    "name": name,
                    "mac": mac,
                    "indoor": True
                },
                "time": station_data.get('date'),
                "fields": {
                    "temperature": float(station_data.get(temp_key)),
                    "humidity": float(station_data.get(hum_key)),
                    "vapor_density": vapor_density(station_data.get(temp_key), station_data.get(hum_key)),
                }
            }
        ]
    return None


def upload_data(host, port, user, password, dbname, data):
    print('Uploading this data:\n')
    pprint.pprint(data)
    client = InfluxDBClient(host, port, user, password, dbname, ssl=True, verify_ssl=False)
    return client.write_points(data)


def get_data(sensor_mapping, application_key, api_key):
    pprint.pprint('Using this sensor mapping: \n' + pprint.pformat(sensor_mapping))

    points = []

    devices = get_devices(application_key, api_key)

    for device in devices:
        # Unpack incoming data.
        data = device['lastData']
        mac = device['macAddress']
        location = device['info'].get('location', device['info']['coords'].get('location'))
        name = device['info']['name']
        # pprint.pprint(data)
        sensor_name = sensor_mapping.get(mac, f'{location} - {name}')

        # Outdoor point
        outdoor_point = transform_outdoor(mac, location, name, sensor_name, data)
        # pprint.pprint(outdoor_point)
        if outdoor_point:
            points = points + outdoor_point

        # Indoor points
        indoor_point = transform_indoor(mac, location, name, sensor_name, data)
        # pprint.pprint(indoor_point)
        points = points + indoor_point
        for num in range(1, 8):
            point = transform_num(mac, location, name, sensor_name, data, num)
            if point:
                points = points + point

    return points


def process_data(sensor_mapping, application_key, api_key, host, port, user, password, dbname):
    points = get_data(sensor_mapping, application_key, api_key)

    if upload_data(host, port, user, password, dbname, points):
        return f'Success!\n'
    else:
        return f'Failed :(\n'


def upload_function(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    application_key = request.args.get('applicationKey', None)
    api_key = request.args.get('apiKey', None)

    sensor_mapping = json.loads(request.environ.get("sensor_mapping", "{}"))
    pprint.pprint('Using this sensor mapping: \n' + pprint.pformat(sensor_mapping))

    host = request.environ.get("influxdb_host")
    port = request.environ.get("influxdb_port")
    user = request.environ.get("influxdb_user")
    password = request.environ.get("influxdb_password")
    dbname = request.environ.get("influxdb_database")

    return process_data(sensor_mapping, application_key, api_key, host, port, user, password, dbname)


if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        return upload_function(request)

    app.run('127.0.0.1', 8000, debug=True)

