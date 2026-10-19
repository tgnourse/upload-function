"""
Pulls the latest readings for every FireBoard on an account and writes them to InfluxDB.

API docs: https://docs.fireboard.io/app/app-api/
The API allows 17 calls per user per 5 minutes and only returns readings less than 60 seconds old, so this is
meant to be called once a minute and makes a single devices.json call per run.
"""

import os
import pprint
import re
import requests
from influxdb import InfluxDBClient

API_URL = 'https://fireboard.io/api/v1/devices.json'
USER_AGENT = 'upload-function/1.0 (+https://github.com/tgnourse/upload-function)'

# degreetype values on readings. 3 isn't in the docs but is what the Beacon humidity channel reports.
CELSIUS = 1
FAHRENHEIT = 2
HUMIDITY = 3


def get_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


def get_devices(token):
    response = requests.get(API_URL, headers={'Authorization': f'Token {token}', 'User-Agent': USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.json()


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


def vapor_density(temperature, humidity):
    if temperature is None or humidity is None:
        return None
    # Same formula as ambient-weather so the values can be compared.
    temp_c = (temperature - 32) * (5.0/9.0)
    saturation_vapor_density = 5.018+0.32321*temp_c+8.1847*0.0081847*temp_c*temp_c+0.00031243*temp_c*temp_c*temp_c
    return (humidity / 100.0) * saturation_vapor_density


def to_fahrenheit(temp, degreetype):
    if degreetype == CELSIUS:
        return temp * 9.0 / 5.0 + 32
    return temp


def transform_device(device, prefix):
    labels = {c['channel']: c['channel_label'] for c in device.get('channels') or []}
    device_log = device.get('device_log') or {}

    temps = [t for t in device.get('latest_temps') or [] if t.get('degreetype') in (CELSIUS, FAHRENHEIT)]
    humidity = next((t for t in device.get('latest_temps') or [] if t.get('degreetype') == HUMIDITY), None)

    points = []
    for reading in temps:
        channel = reading['channel']
        label = labels.get(channel, f'Channel {channel}')
        temperature = float(to_fahrenheit(reading['temp'], reading['degreetype']))
        fields = {'temperature': temperature}

        # Humidity and device health go on channel 1, which is the onboard ambient sensor on the Beacons.
        if channel == 1:
            if humidity:
                fields['humidity'] = float(humidity['temp'])
                fields['vapor_density'] = vapor_density(temperature, fields['humidity'])
            if device_log.get('vBattPer') is not None:
                fields['battery_status'] = float(device_log['vBattPer'])
            if device_log.get('signallevel') is not None:
                fields['signal_level'] = float(device_log['signallevel'])

        points.append({
            'measurement': 'environment_sensor',
            'tags': {
                'sensor_id': f"{prefix}_{slug(device['title'])}_{slug(label)}",
                'original_sensor_id': f"{device['hardware_id']}_{channel}",
                'name': device['title'],
                'label': label,
                'model': device.get('model_name') or device.get('model'),
            },
            'time': reading['created'],
            'fields': fields,
        })
    return points


def upload_data(host, port, user, password, dbname, points):
    print('Uploading this data:')
    pprint.pprint(points)
    client = InfluxDBClient(host, int(port), user, password, dbname, ssl=True, verify_ssl=False)
    return client.write_points(points, time_precision='s')


def upload_function(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    token = get_env('fireboard_token')
    host = get_env('influxdb_host')
    port = get_env('influxdb_port')
    user = get_env('influxdb_user')
    password = get_env('influxdb_password')
    dbname = get_env('influxdb_database')
    prefix = os.environ.get('sensor_id_prefix', 'fireboard')

    try:
        devices = get_devices(token)
    except requests.HTTPError as e:
        # 429 means we're over the 17 calls / 5 minutes limit; don't retry, the next scheduled run will.
        print(f'FireBoard API error: {e}')
        return f'FireBoard API error: {e.response.status_code}\n', 502

    points = []
    for device in devices:
        points += transform_device(device, prefix)

    if not points:
        return 'No current readings.\n'
    if upload_data(host, port, user, password, dbname, points):
        return f'Success! Wrote {len(points)} points.\n'
    return 'Failed :(\n', 500
