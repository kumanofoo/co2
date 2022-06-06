pub mod ds18b20;
use paho_mqtt as mqtt;
use serde::Deserialize;
use std::time::Duration;
use std::{env, fs::File, io, io::BufReader, num};

#[derive(Debug)]
pub enum SensorError {
    Io(io::Error),
    Parse(num::ParseIntError),
    BadConnection,
    SensorNotFound,
}

impl From<io::Error> for SensorError {
    fn from(err: io::Error) -> SensorError {
        SensorError::Io(err)
    }
}

impl From<num::ParseIntError> for SensorError {
    fn from(err: num::ParseIntError) -> SensorError {
        SensorError::Parse(err)
    }
}

pub trait Sensor<T> {
    fn new() -> Result<T, SensorError>;
    fn read_temp(&self) -> Result<u32, SensorError>;
}

pub const CONFIG_KEY: &str = "DS18B20_CONFIG";
pub const DEFAULT_CONFIG_FILE: &str = "./ds18b20.json";

#[derive(Deserialize, Debug, Clone)]
pub struct Config {
    pub broker_uri: String,
    pub topic: String,
    pub client_id: String,
    pub interval_secs: u64,
}

impl Config {
    pub fn new() -> Result<Config, String> {
        //! Read config file 'ds18b20.json' and create a new Config.
        //! The config file can also be specified by environment variables.

        let config_file = env::var(CONFIG_KEY).unwrap_or(DEFAULT_CONFIG_FILE.to_string());
        Config::read_config(&config_file)
    }

    pub fn read_config(filename: &str) -> Result<Config, String> {
        //! Read config file _filename_ and create a new Config.

        let file = match File::open(filename) {
            Ok(file) => file,
            Err(why) => return Err(why.to_string()),
        };
        let reader = BufReader::new(file);
        let _config: Config = match serde_json::from_reader(reader) {
            Ok(config) => config,
            Err(why) => return Err(why.to_string()),
        };

        Ok(Config {
            broker_uri: _config.broker_uri,
            topic: _config.topic,
            client_id: _config.client_id,
            interval_secs: _config.interval_secs,
        })
    }
}

pub struct Publisher {
    pub client: mqtt::Client,
    pub config: Config,
}

impl Publisher {
    pub fn new() -> Result<Publisher, ()> {
        //! Create a new MQTT client.

        let config = Config::new().unwrap();

        log::info!("broker_uri: {}", config.broker_uri);
        log::info!("client_id: {}", config.client_id);
        log::info!("topic: {}", config.topic);

        let create_opts = mqtt::CreateOptionsBuilder::new()
            .server_uri(&config.broker_uri)
            .client_id(&config.client_id)
            .finalize();

        // Create a client.
        let cli = mqtt::Client::new(create_opts).unwrap();

        // Define the set of options for the connection.
        let conn_opts = mqtt::ConnectOptionsBuilder::new()
            .keep_alive_interval(Duration::from_secs(20))
            .clean_session(true)
            .finalize();

        if let Err(e) = cli.connect(conn_opts) {
            log::error!("Unable to connect:\n\t{:?}", e);
        }

        Ok(Publisher {
            client: cli,
            config: config,
        })
    }

    pub fn publish(&self, message: &str) -> Result<(), String> {
        //! Publish message.
        let qos = 1;
        let msg = mqtt::Message::new(&self.config.topic, message, qos);
        if let Err(e) = self.client.publish(msg) {
            return Err(format!("Error sending message: {:?}", e));
        }
        Ok(())
    }

    pub fn disconnect(&self) {
        //! Disconnect MQTT client.
        self.client.disconnect(None).unwrap();
    }
}
