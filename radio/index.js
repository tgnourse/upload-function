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

    const measurement = 'atmospheric_noise';

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
                    fft_level: Influx.FieldType.FLOAT,
                    rms_level: Influx.FieldType.FLOAT,
                },
                tags: [ 'site', 'band', 'receiver' ]
            }
        ]
    });

    // Some hard coded data for testing without query parameters.
    // const temperature = 81.316319523919;
    // const humidity = 43.363088426032;
    // const heap = 33752;
    // const ip = '192.168.1.132';
    // const ssid = 'Blinky';
    // const sensor_id = 'tgnourse12';

    // Collect the data from the HTTP request query parameters.
    console.log('Query Parameters:');
    console.log(req.query);
    const timestamp_ns = req.query['timestamp_ns'];
    const fft_level = req.query['fft_level'];
    const rms_level = req.query['rms_level'];
    const site = req.query['site'];
    const band = req.query['band'];
    const receiver = req.query['receiver'];

    const point = {
        timestamp: timestamp_ns,
        measurement: measurement,
        fields: {
            fft_level: fft_level,
            rms_level: rms_level
        }, tags: {
            site: site,
            band: band,
            receiver: receiver
        }
    };

    console.log('Going to write this point to InfluxDB:');
    console.log(point);

    // Go ahead and write the data.
    influx.writePoints([point])
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

    // Code for querying. Use for debugging if needed but note that the user might not have READ
    // access.
    // console.log('Attempting to query latest data.');
    // influx.query(`select * from ${measurement} limit 1`)
    //     .then(result => {
    //         console.log('Results were fetched ... returning.');
    //         res.status(200).json(result)
    //     }).catch(err => {
    //     res.status(500).send(`Error querying data from InfluxDB! ${err.stack}`)
    // });
    // console.log('Query was attempted ... ');
};