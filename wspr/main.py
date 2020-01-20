# Clone of the WSPRnet interface for bulk and single upload.


import pprint
import datetime
from influxdb import InfluxDBClient


def upload_data(host, port, user, password, dbname, data):
    print('Uploading this data to InfluxDB:')
    pprint.pprint(data)
    client = InfluxDBClient(host, int(port), user, password, dbname, ssl=True, verify_ssl=False)
    return client.write_points(data, time_precision='ms')


def convert_time(date, time):
    # date: 200119 YYMMDD
    # time: 2002 HHMM
    d = datetime.datetime.strptime(date + time, '%y%m%d%H%M')
    return int(d.timestamp())


def process_data(host, port, user, password, dbname, receive, spots):
    print('Processing data ...')
    print('receive: ')
    pprint.pprint(receive)
    print('spots: ')
    pprint.pprint(spots)

    points = []

    for spot in spots:
        point = {
         'measurement': 'spot',
         'tags': {
             'rcall': receive.get('rcall'),
             'rgrid': receive.get('rgrid'),
             'rqrg': receive.get('rqrg'),
             'tqrg': spot.get('tqrg'),
             'tcall': spot.get('tcall'),
             'tgrid': spot.get('tgrid'),
             'dbm': spot.get('dbm'),
             'version': receive.get('rversion'),
             'mode': spot.get('mode'),
         },
         'fields': {
             'sig': float(spot.get('sig')),
             'dt': float(spot.get('dt')),
             'drift': float(spot.get('drift')),
         },
         'time': convert_time(spot['date'], spot['time'])
        }
        points.append(point)

    if upload_data(host, port, user, password, dbname, points):
        return f'Success!\n'
    else:
        return f'Failed :(\n'


def convert_file(f):
    return []


def upload_function(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    # Pull data from the HTTP request
    # application_key = request.args.get('applicationKey', None)
    # api_key = request.args.get('apiKey', None)

    receive = {}
    spots = []

    if request.method == 'POST':  # Bulk upload.
        # Required parameters.
        receive['rcall'] = request.form['call']
        receive['rgrid'] = request.form['grid']

        # Optional parameters
        receive['rqrg'] = request.form.get('qrg')
        receive['rversion'] = request.form.get('version')

        # Convert the file to a list.
        allmept = request.files['allmept']
        spots = convert_file(allmept)

    else:  # Single upload assumes GET
        '''
            Reference cURL
            curl "http://localhost:8000/&\
                rcall=KI6NKO&\
                rgrid=CM87&\
                rqrg=${recording_band_center_mhz}&\
                date=${signal_date}&\
                time=${signal_time}&\
                sig=${signal_snr}&\
                dt=${signal_dt}&\
                drift=${signal_drift}&\
                tqrg=${signal_freq}&\
                tcall=${signal_call}&\
                tgrid=${signal_grid}&\
                dbm=${signal_pwr}&\
                version=WD-${VERSION}&\
                mode=2"
        '''

        # Required parameters.
        receive['rcall'] = request.args['rcall']
        receive['rgrid'] = request.args['rgrid']

        # Optional parameters.
        receive['rqrg'] = request.args.get('rqrg')
        receive['rversion'] = request.args.get('version')

        # The single spot.
        spots.append({
            'date': request.args.get('date'),
            'time': request.args.get('time'),
            'sig': request.args.get('sig'),
            'dt': request.args.get('dt'),
            'drift': request.args.get('drift'),
            'tqrg': request.args.get('tqrg'),
            'tcall': request.args.get('tcall'),
            'tgrid': request.args.get('tgrid'),
            'dbm': request.args.get('dbm'),
            'mode': request.args.get('mode'),
        })

    # Pull data from the environmental variables
    host = request.environ.get("influxdb_host")
    port = request.environ.get("influxdb_port")
    user = request.environ.get("influxdb_user")
    password = request.environ.get("influxdb_password")
    dbname = request.environ.get("influxdb_database")

    print("Host: " + host)
    print("Port: " + port)
    print("User: " + user)
    print("Database: " + dbname)

    return process_data(host, port, user, password, dbname, receive, spots)


if __name__ == "__main__":
    from flask import Flask, request
    app = Flask(__name__)

    @app.route('/')
    def index():
        return upload_function(request)

    app.run('127.0.0.1', 8000, debug=True)

