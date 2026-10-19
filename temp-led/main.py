from influxdb import InfluxDBClient
import os
import pprint

TYPE_TEMPERATURE = 'temperature'


def get_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


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
    }

    config = configurations[id]

    if config['type'] == TYPE_TEMPERATURE:
        influx_host = get_env("influxdb_host")
        influx_port = get_env("influxdb_port")
        influx_user = get_env("influxdb_user")
        influx_password = get_env("influxdb_password")
        influx_dbname = get_env("influxdb_database")
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
    else:
        return str({'red': 0, 'green': 0, 'blue': 0})  # Off


# Debug server that can be called directly. Set the influxdb_* environment variables first.
# python3 main.py
# curl 'http://localhost:8000/?id=1'
if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        return get_function(request)

    app.run('127.0.0.1', 8000, debug=True)

