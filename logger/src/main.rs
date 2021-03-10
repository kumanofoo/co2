use chrono::Utc;
use paho_mqtt as mqtt;
use rusqlite::NO_PARAMS;
use rusqlite::{params, Connection, Result};
use std::{env, process, thread, time::Duration};

fn on_connect_success(cli: &mqtt::AsyncClient, _msgid: u16) {
    println!("Connection succeeded");
    let data = cli.user_data().unwrap();

    if let Some(topic) = data.downcast_ref::<String>() {
        println!("Subscribing to topic: {}", topic);
        cli.subscribe(topic, 1);
    }
}

fn on_connect_failure(cli: &mqtt::AsyncClient, _msgid: u16, rc: i32) {
    println!("Connection attempt failed with error code {}.\n", rc);
    thread::sleep(Duration::from_millis(2500));
    cli.reconnect_with_callbacks(on_connect_success, on_connect_failure);
}

fn insert_into_database(conn: &Connection, topic: &str, payload: &str) -> Result<()> {
    let timestamp: i64 = Utc::now().format("%s%f").to_string().parse().unwrap();
    conn.execute(
        "INSERT INTO measurement (timestamp, topic, payload) VALUES (?1, ?2, ?3)",
        params![timestamp, topic, payload],
    )?;
    Ok(())
}

fn get_config<N: AsRef<str>>(key: N) -> String {
    match env::var(key.as_ref()) {
        Ok(val) => val,
        Err(_) => {
            println!("no environment variable '{}'", key.as_ref());
            process::exit(1);
        }
    }
}

fn main() -> Result<()> {
    env_logger::init();
    let broker_uri = get_config("CO2DB_BROKER_URI");
    let topic = get_config("CO2DB_TOPIC");
    let database = get_config("CO2DB_DATABASE");
    let client_id = get_config("CO2DB_CLIENT_ID");
    log::info!("broker_uri: {}", broker_uri);
    log::info!("topic: {}", topic);
    log::info!("database: {}", database);

    let conn = Connection::open(database)?;
    conn.execute(
        "CREATE TABLE IF NOT EXISTS measurement (
            timestamp INTEGER PRIMARY KEY,
            topic TEXT,
            payload TEXT
        );",
        NO_PARAMS,
    )?;

    let create_opts = mqtt::CreateOptionsBuilder::new()
        .server_uri(broker_uri)
        .client_id(client_id)
        .user_data(Box::new(topic))
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

    cli.set_message_callback(move |_cli, mesg| {
        if let Some(msg) = mesg {
            let topic: &str = msg.topic();
            let payload_str: &str = &msg.payload_str();

            log::debug!("{} - {}", topic, payload_str);
            match insert_into_database(&conn, topic, payload_str) {
                Err(err) => panic!("{}", err),
                _ => (),
            }
        }
    });

    let conn_opts = mqtt::ConnectOptionsBuilder::new()
        .keep_alive_interval(Duration::from_secs(20))
        .mqtt_version(mqtt::MQTT_VERSION_3_1_1)
        .clean_session(true)
        .finalize();

    println!("Connecting to the MQTT server...");
    cli.connect_with_callbacks(conn_opts, on_connect_success, on_connect_failure);

    loop {
        thread::sleep(Duration::from_millis(1000));
    }
}
