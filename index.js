const Influx = require('influx');

/**
 * Responds to any HTTP request.
 *
 * @param {!express:Request} req HTTP request context. See http://expressjs.com/en/api.html#req
 * @param {!express:Response} res HTTP response context.
 */
exports.helloWorld = (req, res) => {
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

    const measurement = 'environment_sensor';

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
                    temperature: Influx.FieldType.FLOAT, // F
                    humidity: Influx.FieldType.FLOAT, // %
                    vapor_density: Influx.FieldType.FLOAT, // g/m^3
                    heap: Influx.FieldType.INTEGER, // B
                },
                tags: [
                    'sensor_id', 'ip', 'ssid'
                ]
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
    const temperature = req.query['temperature'];
    const humidity = req.query['hum'];
    const heap = req.query['heap'];
    const ip = req.query['ip'];
    const ssid = req.query['ssid'];
    const sensor_id = req.query['sensor_id'];

    // Below this is calculated.
    const temp_c = (temperature - 32) * (5.0/9.0);
    const saturation_vapor_density = 5.018+0.32321*temp_c+8.1847*0.0081847*temp_c*temp_c+0.00031243*temp_c*temp_c*temp_c;
    const vapor_density = (humidity / 100.0) * saturation_vapor_density;

    const point = {
        measurement: measurement,
        fields: {
            temperature: temperature,
            humidity: humidity,
            vapor_density: vapor_density,
            heap: heap
        }, tags: { sensor_id: sensor_id, ip: ip, ssid: ssid }
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

    // Code for querying.
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