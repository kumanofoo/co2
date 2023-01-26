use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::post, Json, Router};
use co2db;
use serde::Deserialize;
use std::net::SocketAddr;
use tokio::signal;
use tokio::sync::mpsc::{channel, Sender};

#[tokio::main]
async fn main() {
    env_logger::init();
    let config = match co2db::Config::read_rest_server() {
        Ok(c) => c,
        Err(e) => {
            log::error!("Failed to read configuration file: {}", e);
            std::process::exit(1);
        }
    };

    log::info!("database: {}", config.database);
    log::info!("table: {}", config.table);
    log::info!("port: {}", config.port);
    log::info!("path: {}", config.path);

    let db = co2db::Co2db::new(&config.database, &config.table).expect("Failed to install DB.");
    let (tx, mut rx) = channel::<Measurement>(32);
    let app = Router::new()
        .route(&config.path, post(post_handler))
        .with_state(tx);
    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));

    log::info!("Starting CO2DB Rest server...");
    tokio::spawn(
        axum::Server::bind(&addr)
            .serve(app.into_make_service())
            .with_graceful_shutdown(shutdown_signal()),
    );
    while let Some(measurement) = rx.recv().await {
        log::debug!("{} - {}", &measurement.topic, &measurement.payload);
        db.insert(&measurement.topic, &measurement.payload).unwrap();
    }

    log::info!("CO2DB REST server exited.");
}

#[derive(Debug, Deserialize)]
struct Measurement {
    topic: String,
    payload: String,
}

async fn post_handler(
    State(tx): State<Sender<Measurement>>,
    Json(input): Json<Measurement>,
) -> impl IntoResponse {
    tx.send(input).await.unwrap();
    StatusCode::OK
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
