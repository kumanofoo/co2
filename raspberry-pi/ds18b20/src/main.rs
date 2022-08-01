use ds18b20::ds18b20::DS18B20;
use ds18b20::{Config, Publisher, Sensor};
use signal_hook::flag;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::sleep;
use std::time::{Duration, Instant};

fn main() {
    env_logger::init();

    let sensor = DS18B20::new().unwrap();
    let publisher = Publisher::new().unwrap();
    let config = Config::new().unwrap();
    let interval_sec = Duration::from_secs(config.interval_secs);
    let term = Arc::new(AtomicBool::new(false));
    flag::register(signal_hook::consts::SIGTERM, Arc::clone(&term)).unwrap();
    log::info!("start.");
    let mut now = Instant::now();
    while !term.load(Ordering::Relaxed) {
        if now.elapsed() > interval_sec {
            let temp = sensor.read_temp().unwrap() as f64 / 1000.0;
            println!("temp: {}", temp);
            if let Err(e) = publisher.publish(&format!("{}", temp)) {
                log::warn!("{:?}", e);
            }
            now = Instant::now();
        }
        sleep(Duration::from_secs(1));
    }
    publisher.disconnect();
    log::info!("terminated.");
}
