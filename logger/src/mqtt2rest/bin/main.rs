use co2db::{self, ConfigRestClient};
use futures::stream::StreamExt;
use paho_mqtt as mqtt;
use reqwest::Url;
use serde::{Deserialize, Serialize};
use std::{process, time::Duration};
use tokio::signal;
use tokio::sync::mpsc::{channel, Receiver, Sender};

#[tokio::main]
async fn main() {
    env_logger::init();
    let config = match co2db::Config::read_rest_client() {
        Ok(c) => c,
        Err(e) => {
            log::error!("Failed to read configuration file: {}", e);
            std::process::exit(1);
        }
    };

    log::info!("broker_uri: {}", config.broker_uri);
    log::info!("topics: {:?}", config.topics);
    log::info!("qos: {:?}", config.qos);
    log::info!("client_id: {}", config.client_id);
    log::info!("url: {}", config.url);

    let (tx, rx) = channel::<Measurement>(32);
    let sub = tokio::spawn(subscriber(tx, config.clone()));
    let cli = tokio::spawn(rest_client(rx, config.url));

    shutdown_signal().await;

    // Abort subscriber and then drop tx. Finally REST client exit.
    sub.abort();
    cli.await.expect("Failed to graceful shutdown.");

    log::info!("CO2DB REST client exited.");
}

#[derive(Serialize, Deserialize, Debug)]
struct Measurement {
    topic: String,
    payload: String,
}

async fn subscriber(tx: Sender<Measurement>, config: ConfigRestClient) {
    // Define the set of options for the create.
    // Use an ID for a presistent session.
    let cfg = config.clone();
    let create_opts = mqtt::CreateOptionsBuilder::new()
        .server_uri(cfg.broker_uri)
        .client_id(cfg.client_id)
        .finalize();

    // Create a client
    let mut cli = mqtt::AsyncClient::new(create_opts).unwrap_or_else(|err| {
        log::error!("Error creating the client: {:?}", err);
        process::exit(1);
    });

    // Get message stream before connecting.
    let mut strm = cli.get_stream(32);

    // Define the set of options for the connection.
    let conn_opts = mqtt::ConnectOptionsBuilder::new()
        .keep_alive_interval(Duration::from_secs(30))
        .mqtt_version(mqtt::MQTT_VERSION_3_1_1)
        .clean_session(true)
        .finalize();

    // Make the connection to the broker
    log::info!("Connecting to the MQTT server...");
    cli.connect(conn_opts)
        .await
        .expect("Failed to connect to broker.");

    log::info!("Subscribeing to topics: {:?}", config.topics);
    cli.subscribe_many(&config.topics, &config.qos)
        .await
        .expect("Failed to subscribe topics.");

    log::info!("Waiting for messages...");

    while let Some(msg_opt) = strm.next().await {
        if let Some(msg) = msg_opt {
            log::debug!("{} - {}", msg.topic(), msg.payload_str());
            tx.send(Measurement {
                topic: msg.topic().to_string(),
                payload: msg.payload_str().to_string(),
            })
            .await
            .expect("Failed to send.");
        } else {
            // A "None" means we were disconnected. Try to reconnect...
            log::warn!("Lost connection. Attempting reconnect.");
            while let Err(err) = cli.reconnect().await {
                log::warn!("Error reconnecting: {}", err);
                tokio::time::sleep(Duration::from_millis(1000)).await;
            }
        }
    }

    log::info!("Subscriber exited.");
}

async fn rest_client(mut rx: Receiver<Measurement>, url: String) {
    let client = reqwest::Client::new();
    let url = Url::parse(&url).unwrap();

    while let Some(msg) = rx.recv().await {
        log::debug!("{:?}", msg);

        match client.post(url.clone()).json(&msg).send().await {
            Ok(resp) => {
                if !resp.status().is_success() {
                    log::warn!("Status Code: {}", resp.status());
                    if let Ok(text) = resp.text().await {
                        log::warn!("\t{}", text);
                    }
                    log::warn!("Could not send a message: {:?}", msg);
                }
            }
            Err(e) => {
                log::warn!("Request Error: {}", e);
                log::warn!("Could not send a message: {:?}", msg);
            }
        }
    }

    log::debug!("REST client exited.");
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler.");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install signal handler.")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            log::info!("SIGINT signal received.");
        },
        _ = terminate => {
            log::info!("SIGTERM signal received.");
        },
    }
}

#[ignore]
#[tokio::test]
async fn test_client() {
    let url = "http://httpbin.org/post";
    let (tx, rx) = channel::<Measurement>(32);
    tokio::spawn(async move {
        for i in 0..5 {
            tx.send(Measurement {
                topic: format!("test_topic{}", i),
                payload: format!("10 20 30 {}", i * 10),
            })
            .await
            .unwrap();
        }
        println!("all data sent.");
    });
    rest_client(rx, url.to_string()).await;
}

/// Test subscriber
/// 
/// # Requirements
/// - MQTT broker
/// - REST server
/// 
/// Store 'test_config_mqtt_client.json' in the 'tests' directory and delete the line '#[ignore]' below.
///  
#[ignore]
#[tokio::test]
async fn test_subscriber() {
    
    let (tx, mut rx) = channel::<Measurement>(32);
    let config = match co2db::Config::read_rest_client_from_file("tests/test_config_mqtt_client.json") {
        Ok(c) => c,
        Err(e) => {
            panic!("configration error: {}", e);
        }
    };
    let topics = config.topics.to_vec();
    let _ = tokio::spawn(subscriber(tx, config));

    for i in 0..2 {
        println!("wait for {}.", i);
        if let Some(msg) = rx.recv().await {
            println!("{:?}", msg);
            assert!(topics.contains(&msg.topic))
        } else {
            panic!("channel is closed.");
        }
    }
}
