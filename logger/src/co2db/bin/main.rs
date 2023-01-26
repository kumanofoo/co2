use co2db;
use paho_mqtt as mqtt;
use signal_hook::flag;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::{process, thread, time::Duration};

fn try_reconnect(cli: &mqtt::Client) -> bool {
    log::warn!("Connection lost. Waiting to retry connection.");
    for _ in 0..12 {
        thread::sleep(Duration::from_millis(5000));
        if cli.reconnect().is_ok() {
            log::warn!("Successfully reconnected.");
            return true;
        }
    }
    log::error!("Unable to reconnect after several attempts.");
    false
}

fn subscribe_topics(cli: &mqtt::Client, topics: &[String], qos: &[i32]) {
    if let Err(err) = cli.subscribe_many(topics, qos) {
        log::error!("Error subscribes topics: {:?}", err);
        process::exit(1);
    }
}

fn main() {
    env_logger::init();
    let config = match co2db::Config::read() {
        Ok(c) => c,
        Err(e) => {
            log::error!("Failed to read configuration file: {}", e);
            std::process::exit(1);
        }
    };
    let cfg = config.clone();

    log::info!("database: {}", config.database);
    log::info!("table: {}", config.table);
    log::info!("broker_uri: {}", config.broker_uri);
    log::info!("topics: {:?}", config.topics);
    log::info!("qos: {:?}", config.qos);
    log::info!("client_id: {}", config.client_id);

    let db = co2db::Co2db::new(&config.database, &config.table).unwrap();

    // Define the set of options for the create.
    // Use an ID for a presistent session.
    let create_opts = mqtt::CreateOptionsBuilder::new()
        .server_uri(cfg.broker_uri)
        .client_id(cfg.client_id)
        .finalize();

    // Create a client
    let cli = mqtt::Client::new(create_opts).unwrap_or_else(|err| {
        log::error!("Error creating the client: {:?}", err);
        process::exit(1);
    });

    // Initialize the consumer before connecting.
    let rx = cli.start_consuming();

    // Define the set of options for the connection.
    let conn_opts = mqtt::ConnectOptionsBuilder::new()
        .keep_alive_interval(Duration::from_secs(20))
        .mqtt_version(mqtt::MQTT_VERSION_3_1_1)
        .clean_session(true)
        .finalize();

    // Connect and wait for it to complete or fail.
    if let Err(err) = cli.connect(conn_opts) {
        log::error!("Unable to connect:\n\t{:?}", err);
        process::exit(1);
    }

    // Subscribe topics.
    subscribe_topics(&cli, &cfg.topics, &cfg.qos);

    // Set signal handler.
    let term = Arc::new(AtomicBool::new(false));
    flag::register(signal_hook::consts::SIGTERM, Arc::clone(&term)).unwrap();
    let countdown_time = Duration::from_secs(1);

    log::info!("Connecting to the MQTT server...");

    // Wait for messages.
    while !term.load(Ordering::Relaxed) {
        if let Ok(data) = rx.recv_timeout(countdown_time) {
            if let Some(mesg) = data {
                let topic: &str = mesg.topic();
                let payload_str: &str = &mesg.payload_str();
                log::debug!("{} - {}", topic, payload_str);
                db.insert(topic, payload_str).unwrap();
            } else {
                log::warn!("Receive something but message:\n\t{:?}", data);
            }
        } else {
            if !cli.is_connected() {
                if try_reconnect(&cli) {
                    log::warn!("Resubscribe topics...");
                    subscribe_topics(&cli, &cfg.topics, &cfg.qos);
                }
            }
        }
    }
    log::info!("co2db terminating...");

    // If still connected, then disconnect now.
    if cli.is_connected() {
        log::info!("Disconnecting...");
        cli.unsubscribe_many(&config.topics).unwrap();
        cli.disconnect(None).unwrap();
    }

    log::info!("co2db Exited.");
}
