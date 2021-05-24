use co2db;
use paho_mqtt as mqtt;
use std::{process, thread, time::Duration};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc::channel, Arc};
use signal_hook::flag;

fn on_connect_success(cli: &mqtt::AsyncClient, _msgid: u16) {
    log::info!("Connection succeeded");
    let data = cli.user_data().unwrap();

    if let Some(topic) = data.downcast_ref::<String>() {
        log::info!("Subscribing to topic: {}", topic);
        cli.subscribe(topic, 1);
    }
}

fn on_connect_failure(cli: &mqtt::AsyncClient, _msgid: u16, rc: i32) {
    log::info!("Connection attempt failed with error code {}.\n", rc);
    thread::sleep(Duration::from_millis(2500));
    cli.reconnect_with_callbacks(on_connect_success, on_connect_failure);
}

fn main() {
    env_logger::init();
    let config = co2db::Config::read().unwrap();

    log::info!("database: {}", config.database);
    log::info!("table: {}", config.table);
    log::info!("broker_uri: {}", config.broker_uri);
    log::info!("topic: {}", config.topic);
    log::info!("client_id: {}", config.client_id);

    let db = co2db::Co2db::new(&config.database, &config.table).unwrap();

    let cfg = config.clone();
    let create_opts = mqtt::CreateOptionsBuilder::new()
        .server_uri(cfg.broker_uri)
        .client_id(cfg.client_id)
        .user_data(Box::new(cfg.topic))
        .finalize();

    let mut cli = mqtt::AsyncClient::new(create_opts).unwrap_or_else(|e| {
        println!("Error creating the client: {:?}", e);
        process::exit(1);
    });

    cli.set_connected_callback(|_cli: &mqtt::AsyncClient| {
        log::info!("Connected.");
    });

    cli.set_connection_lost_callback(|cli: &mqtt::AsyncClient| {
        log::info!("Connection lost. Attempting reconnect.");
        thread::sleep(Duration::from_millis(2500));
        cli.reconnect_with_callbacks(on_connect_success, on_connect_failure);
    });

    let (tx, rx) = channel();
    cli.set_message_callback(move |_cli, mesg| {
        let m = mesg.unwrap();
        tx.send(m).unwrap();
    });

    let conn_opts = mqtt::ConnectOptionsBuilder::new()
        .keep_alive_interval(Duration::from_secs(20))
        .mqtt_version(mqtt::MQTT_VERSION_3_1_1)
        .clean_session(true)
        .finalize();

    log::info!("Connecting to the MQTT server...");
    cli.connect_with_callbacks(conn_opts, on_connect_success, on_connect_failure);

    let term = Arc::new(AtomicBool::new(false));
    flag::register(signal_hook::consts::SIGTERM, Arc::clone(&term)).unwrap();
    let countdown_time = Duration::from_secs(5);
    while !term.load(Ordering::Relaxed) {
        if let Ok(mesg) = rx.recv_timeout(countdown_time) {
            let topic: &str = mesg.topic();
            let payload_str: &str = &mesg.payload_str();

            log::debug!("{} - {}", topic, payload_str);
            db.insert(topic, payload_str).unwrap();
        }
    }

    log::info!("co2db terminated.");
}
