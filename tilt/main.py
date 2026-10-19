"""
Receives readings from a Tilt Pico (Tilt hydrometer Wi-Fi bridge) and writes them to InfluxDB.

The Tilt Pico posts to its "custom cloud URL" as application/x-www-form-urlencoded, e.g.
    Timepoint=43331.793&Temp=65.0&SG=1.010&Beer=Munich%20Lager%20#1&Color=PINK&Comment=
See https://github.com/baronbrew/TiltPico. Temp is in F and SG is specific gravity at 60 F. In practice Color
also carries the Tilt's ID, e.g. RED:CAFD39B487D5.

The Pico can't authenticate, so the function is public and requires ?key=<tilt_key> on the URL.
"""

import hmac
import json
import os
import re
from influxdb import InfluxDBClient

MEASUREMENT = 'tilt'


def get_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


def brix(sg):
    # Standard polynomial conversion from specific gravity to degrees Brix.
    return ((182.4601 * sg - 775.6821) * sg + 1262.7794) * sg - 669.5622


def build_point(form, prefix):
    color, _, tilt_id = (form.get('Color') or '').strip().partition(':')
    if not color:
        raise ValueError('missing Color')
    temperature = float(form['Temp'])  # F
    sg = float(form['SG'])

    tags = {'sensor_id': f'{prefix}_{slug(color)}', 'color': color.upper()}
    if tilt_id:
        tags['tilt_id'] = tilt_id
    # The Pico appends its log ID to the beer name, e.g. "2026 Zin Lite,298956"; the app's own posts don't.
    beer, _, log_id = (form.get('Beer') or '').strip().rpartition(',')
    if not log_id.isdigit():
        beer, log_id = (form.get('Beer') or '').strip(), ''
    if beer:
        tags['beer'] = beer.strip()
    if log_id:
        tags['log_id'] = log_id

    return {
        'measurement': MEASUREMENT,
        'tags': tags,
        'fields': {
            'temperature': temperature,
            'specific_gravity': sg,
            'brix': brix(sg),
        },
    }


def upload_function(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    if not hmac.compare_digest(request.args.get('key', ''), get_env('tilt_key')):
        return 'Forbidden\n', 403

    # Never log request.args: it contains the key.
    form = request.form if request.form else request.args
    print(f"Tilt data from {request.headers.get('User-Agent', '')}: "
          f"{json.dumps({k: v for k, v in form.items() if k != 'key'})}")

    try:
        point = build_point(form, os.environ.get('sensor_id_prefix', 'tilt'))
    except KeyError as e:
        return f'Bad request: missing {e.args[0]}\n', 400
    except ValueError as e:
        return f'Bad request: {e}\n', 400

    print(f'Writing to InfluxDB: {json.dumps(point)}')

    client = InfluxDBClient(get_env('influxdb_host'), int(get_env('influxdb_port')), get_env('influxdb_user'),
                            get_env('influxdb_password'), get_env('influxdb_database'), ssl=True, verify_ssl=False)
    try:
        client.write_points([point])
    except Exception as e:
        print(f'Error saving data to InfluxDB! {e!r}')
        return 'Error saving data to InfluxDB!\n', 500

    return 'Success!\n'
