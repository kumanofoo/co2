use paho_mqtt as mqtt;
use std::{process, thread, time::Duration};

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

fn main() {
    let host = "tcp://192.168.8.4:1883";
    let topic: String = "living/SCD30".to_string();

    let create_opts = mqtt::CreateOptionsBuilder::new()
        .server_uri(host)
        .client_id("logger01")
        .user_data(Box::new(topic))
        .finalize();

    let mut cli = mqtt::AsyncClient::new(create_opts).unwrap_or_else(|e| {
        println!("Error creating the client: {:?}", e);
        process::exit(1);
    });

    cli.set_connected_callback(|_cli: &mqtt::AsyncClient| {
        println!("Connected.");
    });

    cli.set_connection_lost_callback(|cli: &mqtt::AsyncClient| {
        println!("Connection lost. Attempting reconnect.");
        thread::sleep(Duration::from_millis(2500));
        cli.reconnect_with_callbacks(on_connect_success, on_connect_failure);
    });

    cli.set_message_callback(|_cli, mesg| {
        if let Some(msg) = mesg {
            let topic = msg.topic();
            let payload_str = msg.payload_str();

            println!("{} - {}", topic, payload_str);
        }
    });

    let lwt = mqtt::Message::new("test", "Async subscriber lost connection", 1);

    let conn_opts = mqtt::ConnectOptionsBuilder::new()
        .keep_alive_interval(Duration::from_secs(20))
        .mqtt_version(mqtt::MQTT_VERSION_3_1_1)
        .clean_session(true)
        .will_message(lwt)
        .finalize();

    println!("Connecting to the MQTT server...");
    cli.connect_with_callbacks(conn_opts, on_connect_success, on_connect_failure);

    let mut i = 0;
    loop {
        println!("{}", i);
        i += 1;
        thread::sleep(Duration::from_millis(1000));
    }
}
