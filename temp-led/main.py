from influxdb import InfluxDBClient
import pprint
import requests

TYPE_TEMPERATURE = 'temperature'
TYPE_AIR_QUALITY = 'air_quality'


def get_data(host, port, user, password, dbname, sensor):
    print('Running this query:')
    query = "SELECT LAST(temperature) FROM environment_sensor WHERE original_sensor_id = '" + sensor + "'"
    print(query)
    print(f'{user}@{host}:{port}/{dbname}')
    client = InfluxDBClient(host, port, user, password, dbname, ssl=True, verify_ssl=False)
    return client.query(query)


def get_function(request):
    id = request.args.get("id")

    configurations = {
        # Bedroom
        '1': {
            'type': TYPE_TEMPERATURE,
            'original_sensor_id': '24:7D:4D:A3:64:EE_1',
            'min': 66.0,
            'max': 74.0,
            'min_color': {
                'red': 0,
                'green': 0,
                'blue': 255
            },
            'max_color': {
                'red': 255,
                'green': 0,
                'blue': 0
                
            },
            'color': {
                'red': 0,
                'green': 255,
                'blue': 0
            }
        },
        # Insulin
        '4': {
            'type': TYPE_TEMPERATURE,
            'original_sensor_id': '24:7D:4D:A3:64:EE_3',
            'min': 33.0,
            'max': 50.0,
            'min_color': {
                'red': 255,
                'green': 0,
                'blue': 0
            },
            'max_color': {
                'red': 255,
                'green': 255,
                'blue': 0
            },
            'color': {
                'red': 0,
                'green': 255,
                'blue': 0
            }
        },
        # Bedroom (Test 7 LED)
        '3': {
            'type': TYPE_TEMPERATURE,
            'original_sensor_id': '24:7D:4D:A3:64:EE_1',
            'min': 66.0,
            'max': 74.0,
            'min_color':
                [
                    {'red': 0, 'green': 0, 'blue': 255},
                    {'red': 0, 'green': 0, 'blue': 255},
                    {'red': 0, 'green': 0, 'blue': 255},
                    {'red': 0, 'green': 0, 'blue': 255},
                    {'red': 0, 'green': 0, 'blue': 255},
                    {'red': 0, 'green': 0, 'blue': 255},
                    {'red': 0, 'green': 0, 'blue': 255},
                ],
            'max_color':
                [
                    {'red': 255, 'green': 0, 'blue': 0},
                    {'red': 255, 'green': 0, 'blue': 0},
                    {'red': 255, 'green': 0, 'blue': 0},
                    {'red': 255, 'green': 0, 'blue': 0},
                    {'red': 255, 'green': 0, 'blue': 0},
                    {'red': 255, 'green': 0, 'blue': 0},
                    {'red': 255, 'green': 0, 'blue': 0},
                ],
            'color':
                [
                    {'red': 0, 'green': 255, 'blue': 0},
                    {'red': 0, 'green': 255, 'blue': 0},
                    {'red': 0, 'green': 255, 'blue': 0},
                    {'red': 0, 'green': 255, 'blue': 0},
                    {'red': 0, 'green': 255, 'blue': 0},
                    {'red': 0, 'green': 255, 'blue': 0},
                    {'red': 0, 'green': 255, 'blue': 0},
                ]
        },
        # Local Air Quality
        '2': {
            'type': TYPE_AIR_QUALITY,
            'url': 'https://www.purpleair.com/json?show=38791',
        },
    }

    config = configurations[id]

    if config['type'] == TYPE_TEMPERATURE:
        influx_host = request.environ.get("influxdb_host")
        influx_port = request.environ.get("influxdb_port")
        influx_user = request.environ.get("influxdb_user")
        influx_password = request.environ.get("influxdb_password")
        influx_dbname = request.environ.get("influxdb_database")
        result = get_data(
            influx_host, influx_port, influx_user, influx_password, influx_dbname, config['original_sensor_id']
        )

        pprint.pprint(result)

        temperature = result.raw['series'][0]['values'][0][1]

        if temperature < configurations[id]['min']:
            return str(configurations[id]['min_color'])
        elif temperature > configurations[id]['max']:
            return str(configurations[id]['max_color'])
        return str(configurations[id]['color'])
    elif config['type'] == TYPE_AIR_QUALITY:
        # AQI Calculation: https://www3.epa.gov/airnow/aqi-technical-assistance-document-sept2018.pdf
        r = requests.get(config['url'])
        result = r.json()

        pprint.pprint(result)

        p_2_5_um = float(result['results'][0]['p_2_5_um'])

        if p_2_5_um <= 12.0:
            return str({'red': 0, 'green': 255, 'blue': 0})  # Green
        elif p_2_5_um <= 35.4:
            return str({'red': 255, 'green': 255, 'blue': 0})  # Yellow
        elif p_2_5_um <= 55.4:
            return str({'red': 255, 'green': 70, 'blue': 0})  # Orange
        elif p_2_5_um <= 150.4:
            return str({'red': 255, 'green': 0, 'blue': 0})  # Red
        else:
            return str({'red': 255, 'green': 0, 'blue': 255})  # Purple
    else:
        return str({'red': 0, 'green': 0, 'blue': 0})  # Off


# Debug server that can be called directly.
# python3 main.py
# curl 'http://localhost:8000/?id=1'
if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        # Note that you'll need to fill these in if needed.
        request.environ["influxdb_host"] = ""
        request.environ["influxdb_port"] = ""
        request.environ["influxdb_user"] = ""
        request.environ["influxdb_password"] = ""
        request.environ["influxdb_database"] = ""
        return get_function(request)

    app.run('127.0.0.1', 8000, debug=True)

