"""

"""
from influxdb import InfluxDBClient


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
        '1': {
            'original_sensor_id': '24:7D:4D:A3:64:EE_1',
            'min': 66.0,
            'max': 71.0,
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
        }
    }

    influx_host = request.environ.get("influxdb_host")
    influx_port = request.environ.get("influxdb_port")
    influx_user = request.environ.get("influxdb_user")
    influx_password = request.environ.get("influxdb_password")
    influx_dbname = request.environ.get("influxdb_database")

    config = configurations[id]

    result = get_data(
        influx_host, influx_port, influx_user, influx_password, influx_dbname, config['original_sensor_id']
    )

    temperature = result.raw['series'][0]['values'][0][1]

    if temperature < configurations[id]['min']:
        return configurations[id]['min_color']
    elif temperature > configurations[id]['max']:
        return configurations[id]['max_color']
    return configurations[id]['color']


# Debug server that can be called directly.
if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        # Note that you'll need to fill these in.
        request.environ["influxdb_host"] = ""
        request.environ["influxdb_port"] = ""
        request.environ["influxdb_user"] = ""
        request.environ["influxdb_password"] = ""
        request.environ["influxdb_database"] = ""
        return get_function(request)

    app.run('127.0.0.1', 8000, debug=True)

