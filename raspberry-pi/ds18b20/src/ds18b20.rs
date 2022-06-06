//! # DS18B20
//! Read temperature from device file 'sys/bus/w1/devices/28-xxxxxxxxxxxx/w1_slave'.
//!
//! Return raw data or temperature in milli degree celsius.

use crate::{Sensor, SensorError};
use std::path::PathBuf;
use std::{fs, io};

static W1_PATH_PREFIX: &str = "/sys/bus/w1/devices";
static W1_PATH_SUFFIX: &str = "w1_slave";

#[derive(Debug)]
pub struct DS18B20 {
    w1_id: String,
}

impl DS18B20 {
    fn read_raw(&self) -> io::Result<String> {
        //! Read DS18B20 and return raw data.

        let mut path = PathBuf::from(W1_PATH_PREFIX);
        path.push(&self.w1_id);
        path.push(W1_PATH_SUFFIX);
        fs::read_to_string(path)
    }
}

impl Sensor<DS18B20> for DS18B20 {
    fn new() -> Result<DS18B20, SensorError> {
        //! Find device file 'w1_slave' and return the DS18B20 instance.

        let dir = PathBuf::from(W1_PATH_PREFIX);
        for entry in fs::read_dir(dir)? {
            let filename = entry?.file_name().into_string().unwrap();
            if filename.contains("28-") {
                return Ok(DS18B20 { w1_id: filename });
            }
        }
        panic!("Unable to find a DS18B20")
    }

    fn read_temp(&self) -> Result<u32, SensorError> {
        //! Read DS18B20 and return temperature in milli degree celsius.

        let temp_data = self.read_raw()?;
        if !temp_data.contains("YES") {
            return Err(SensorError::BadConnection);
        }
        let (_, temp_str) = temp_data.split_at(temp_data.find("t=").unwrap() + 2);
        let temp_u32 = temp_str.trim().parse::<u32>()?;
        Ok(temp_u32)
    }
}
