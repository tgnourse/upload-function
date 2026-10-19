"""
Receives readings from the Wemos environment sensors and writes them to InfluxDB.

Python port of the original Node.js uploadFunction (index.js).
"""

import json
import os
import pprint
from influxdb import InfluxDBClient

MEASUREMENT = 'environment_sensor'


def get_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


def load_sensor_mapping():
    # Maps between sensor_id and a better name for that sensor. Note that it doesn't do anything
    # special to check for overlap, etc.
    sensor_mapping_str = os.environ.get('sensor_mapping')
    try:
        sensor_mapping = json.loads(sensor_mapping_str)
        print(f'Using this sensor mapping: {json.dumps(sensor_mapping)}')
        return sensor_mapping
    except (TypeError, ValueError) as e:
        print(f'Problem parsing sensor_mapping env variable: "{sensor_mapping_str}" with error {e}')
        return {}


def to_float(value):
    return float(value) if value not in (None, '') else None


def to_int(value):
    return int(float(value)) if value not in (None, '') else None


def vapor_density(temperature, humidity):
    if temperature is None or humidity is None:
        return None
    # Same formula as ambient-weather so the values can be compared.
    temp_c = (temperature - 32) * (5.0/9.0)
    saturation_vapor_density = 5.018+0.32321*temp_c+8.1847*0.0081847*temp_c*temp_c+0.00031243*temp_c*temp_c*temp_c
    return (humidity / 100.0) * saturation_vapor_density


def without_none(d):
    return {k: v for k, v in d.items() if v is not None}


def build_points(args, sensor_mapping):
    temperature = to_float(args.get('temperature'))  # F
    humidity = to_float(args.get('hum'))  # %
    heap = to_int(args.get('heap'))  # B
    ip = args.get('ip')
    ssid = args.get('ssid')
    sensor_id = args.get('sensor_id')
    pressure = to_float(args.get('pressure'))  # inHg
    pressure_temperature = to_float(args.get('pressure_temperature'))  # F

    # Some devices don't nil out the pressure data correctly. Correct it here.
    if args.get('pressure_temperature') == '55.13':
        pressure = None
        pressure_temperature = None

    # Alias the sensor_id if necessary.
    sensor_id_alias = sensor_mapping.get(sensor_id, sensor_id)

    point = {
        'measurement': MEASUREMENT,
        'tags': without_none({'sensor_id': sensor_id_alias, 'original_sensor_id': sensor_id, 'ip': ip, 'ssid': ssid}),
        'fields': without_none({
            'temperature': temperature,
            'humidity': humidity,
            'vapor_density': vapor_density(temperature, humidity),
            'pressure': pressure,
            'pressure_temperature': pressure_temperature,
            'heap': heap,
        }),
    }
    points = [point]

    # If there's a pressure value, add a separate point for that. This is so the temperatures can be directly compared.
    if pressure:
        points.append({
            'measurement': MEASUREMENT,
            'tags': without_none({
                'sensor_id': f'{sensor_id_alias}_pressure', 'original_sensor_id': sensor_id, 'ip': ip, 'ssid': ssid
            }),
            'fields': without_none({
                'temperature': pressure_temperature,
                'pressure': pressure,
                'pressure_temperature': pressure_temperature,
                'heap': heap,
            }),
        })

    return points


def upload_function(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    host = get_env('influxdb_host')
    port = get_env('influxdb_port')
    user = get_env('influxdb_user')
    password = get_env('influxdb_password')
    dbname = get_env('influxdb_database')
    sensor_mapping = load_sensor_mapping()

    print('Query Parameters:')
    pprint.pprint(request.args.to_dict())

    try:
        points = build_points(request.args, sensor_mapping)
    except ValueError as e:
        return f'Bad request: {e}\n', 400

    print('Going to write these points to InfluxDB:')
    pprint.pprint(points)

    # verify_ssl=False because the InfluxDB certificate is self signed.
    client = InfluxDBClient(host, int(port), user, password, dbname, ssl=True, verify_ssl=False)
    try:
        client.write_points(points)
    except Exception as e:
        print(f'Error saving data to InfluxDB! {e!r}')
        return f'Error saving data to InfluxDB! {e}\n', 500

    print('Successfully wrote!')
    return (f'Successfully wrote to https://{host}:{port}/{dbname} as {user} with this data:\n'
            f'{json.dumps(points[0])}')
