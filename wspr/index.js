const Influx = require('influx');

/**
 * Responds to any HTTP request.
 *
 * @param {!express:Request} req HTTP request context. See http://expressjs.com/en/api.html#req
 * @param {!express:Response} res HTTP response context.
 */
exports.uploadFunction = (req, res) => {
    const influxdb_user = process.env.influxdb_user;
    const influxdb_password = process.env.influxdb_password;
    const influxdb_host = process.env.influxdb_host;
    const influxdb_port = process.env.influxdb_port;
    const influxdb_database = process.env.influxdb_database;

    const influxdb_protocol = 'https';

    console.log('Setting up InfluxDB connection with' +
        ' user:' + influxdb_user +
        ' host:' + influxdb_host +
        ' port:' + influxdb_port +
        ' database:' + influxdb_database);

    // Tell node to ignore TLS rejections because the InfluxDB certificate is self signed.
    process.env['NODE_TLS_REJECT_UNAUTHORIZED'] = 0;

    const measurement = 'spot';

    /*
        curl "http://wsprnet.org/post?
            rcall=${my_call_sign}&
            rgrid=${my_grid}&
            rqrg=${recording_band_center_mhz}&
            tqrg=${signal_freq}&
            tcall=${signal_call}&
            tgrid=${signal_grid}&
            dbm=${signal_pwr}&
            version=WD-${VERSION}&

            sig=${signal_snr}&
            dt=${signal_dt}&
            drift=${signal_drift}&

        # Leaving these out for now
        function=wspr&
        date=${signal_date}&
        time=${signal_time}&
        mode=2
     */

    const influx = new Influx.InfluxDB({
        host: influxdb_host,
        port: influxdb_port,
        protocol: influxdb_protocol,
        username: influxdb_user,
        password: influxdb_password,
        database: influxdb_database,
        schema: [
            {
                measurement: measurement,
                fields: {
                    sig: Influx.FieldType.FLOAT,
                    dt: Influx.FieldType.FLOAT,
                    drift: Influx.FieldType.FLOAT,
                },
                tags: [ 'rcall', 'rgrid', 'rqrg', 'tqrg', 'tcall', 'tgrid', 'dbm', 'version' ]
            }
        ]
    });

    // Collect the data from the HTTP request query parameters.
    console.log('Query Parameters:');
    console.log(req.query);
    // const timestamp_ms = req.query['timestamp_ms'];

    const sig = req.query['sig'];
    const dt = req.query['dt'];
    const drift = req.query['drift'];

    const rcall = req.query['rcall'];
    const rgrid = req.query['rgrid'];
    const rqrg = req.query['rqrg'];
    const tqrg = req.query['tqrg'];
    const tcall = req.query['tcall'];
    const tgrid = req.query['tgrid'];
    const dbm = req.query['dbm'];
    const version = req.query['version'];

    const point = {
        // timestamp: timestamp_ms,
        measurement: measurement,
        fields: {
            sig: sig,
            dt: dt,
            drift: drift,
        }, tags: {
            rcall: rcall,
            rgrid: rgrid,
            rqrg: rqrg,
            tqrg: tqrg,
            tcall: tcall,
            tgrid: tgrid,
            dbm: dbm,
            version: version,
        }
    };

    console.log('Going to write this point to InfluxDB:');
    console.log(point);

    // Go ahead and write the data.
    influx.writePoints([point], { precision: 'ms' })
        .catch(err => {
            console.error(`Error saving data to InfluxDB! ${err.stack}`);
            res.status(500).send(`Error saving data to InfluxDB! ${err.stack}`)
        }).then(() => {
            // TODO: Figure out how to send this only on success, it works as is but it's confusing.
            console.log('Successfully wrote!');
            res.status(200).send(`Successfully wrote to ` +
                `${influxdb_protocol}://${influxdb_host}:${influxdb_port}/${influxdb_database} ` +
                `as ${influxdb_user} with this data:` +
                `\n${JSON.stringify(point)}`);
        });
};
