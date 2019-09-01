"""
API requests are capped at 1 request/second for each user's apiKey and 3 requests/second per applicationKey.
When this limit is exceeded, the API will return a 429 response code. Please be kind to our servers :)
"""

import pprint
from influxdb import InfluxDBClient
import requests


def get_data(application_key, api_key, mac):
    url = f'https://api.ambientweather.net/v1/devices/{mac}?apiKey={api_key}&applicationKey={application_key}&limit=1'

    response = requests.get(url)
    if response:
        return response.json()
    else:
        return None


def vapor_density(temperature, humidity):
    temp_c = (temperature - 32) * (5.0/9.0)
    saturation_vapor_density = 5.018+0.32321*temp_c+8.1847*0.0081847*temp_c*temp_c+0.00031243*temp_c*temp_c*temp_c
    return (humidity / 100.0) * saturation_vapor_density


def transform_outdoor(mac, model, station_data):
    return [
        {
            "measurement": "environment_sensor",
            "tags": {
                "sensor_id": mac + "_outdoor",
                "original_sensor_id": mac + "_outdoor",
                "mac": mac,
                "model": model,
                "outdoor": True
            },
            "time": station_data.get('date'),
            "fields": {
                "temperature": float(station_data.get('tempf')),
                "humidity": float(station_data.get('humidity')),
                "vapor_density": vapor_density(station_data.get('tempf'), station_data.get('humidity')),
                "pressure": float(station_data.get('baromabsin')),
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
                "battery_status": float(station_data.get('battout'))
            }
        }
    ]


def transform_indoor(mac, model, station_data):
    return [
        {
            "measurement": "environment_sensor",
            "tags": {
                "sensor_id": mac + "_indoor",
                "original_sensor_id": mac + "_indoor",
                "mac": mac,
                "model": model,
                "indoor": True
            },
            "time": station_data.get('date'),
            "fields": {
                "temperature": float(station_data.get('tempinf')),
                "humidity": float(station_data.get('humidityin')),
                "vapor_density": vapor_density(station_data.get('tempinf'), station_data.get('humidityin')),
                "pressure": float(station_data.get('baromabsin')),
            }
        }
    ]


def upload_data(host, port, user, password, dbname, data):
    client = InfluxDBClient(host, port, user, password, dbname, ssl=True, verify_ssl=False)
    return client.write_points(data)


def hello_world(request):
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
    mac = request.args.get('mac', None)
    model = request.args.get('model', None)

    sensor_mapping = request.environ.get("sensor_mapping", {})
    pprint.pprint('Using this sensor mapping: \n' + pprint.pformat(sensor_mapping))

    data = get_data(application_key, api_key, mac)
    pprint.pprint(data)
    outdoor_point = transform_outdoor(mac, model, data[0])
    pprint.pprint(outdoor_point)
    indoor_point = transform_indoor(mac, model, data[0])
    pprint.pprint(outdoor_point)

    host = request.environ.get("influxdb_host")
    port = request.environ.get("influxdb_port")
    user = request.environ.get("influxdb_user")
    password = request.environ.get("influxdb_password")
    dbname = request.environ.get("influxdb_database")

    if upload_data(host, port, user, password, dbname, outdoor_point + indoor_point):
        return f'Success!\n'
    else:
        return f'Failed :(\n'


if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        return hello_world(request)

    app.run('127.0.0.1', 8000, debug=True)

