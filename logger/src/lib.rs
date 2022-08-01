use chrono::{DateTime, Duration, TimeZone, Utc};
use rusqlite::{params, Connection, Result};
use serde::Deserialize;
use std::{env, fs, fs::File, io::BufReader, path::Path};

pub const CONFIG_KEY: &str = "CO2DB_CONFIG";
pub const DEFAULT_CONFIG_FILE: &str = "./co2db.json";
pub const DEFAULT_DATABASE: &str = "./co2.db";
pub const DEFAULT_TABLE: &str = "measurement";
pub const DEFAULT_QOS: i32 = 1;

#[derive(Deserialize, Debug, Clone)]
struct _Config {
    database: Option<String>,
    table: Option<String>,
    broker_uri: String,
    topics: Vec<String>,
    qos: Option<Vec<i32>>,
    client_id: String,
}

#[derive(Deserialize, Debug, Clone)]
pub struct Config {
    pub database: String,
    pub table: String,
    pub broker_uri: String,
    pub topics: Vec<String>,
    pub qos: Vec<i32>,
    pub client_id: String,
}

impl Config {
    pub fn read_from_file(filename: &str) -> Result<Config, String> {
        let file = match File::open(filename) {
            Ok(file) => file,
            Err(why) => return Err(why.to_string()),
        };
        let reader = BufReader::new(file);
        let _config: _Config = match serde_json::from_reader(reader) {
            Ok(config) => config,
            Err(why) => return Err(why.to_string()),
        };
        let topic_n = _config.topics.len();
        let qos = match _config.qos {
            Some(qos) => {
                if qos.len() != topic_n {
                    return Err("The QoS list must match topics".to_string());
                }
                qos
            }
            None => vec![DEFAULT_QOS; topic_n],
        };

        // set default if need
        Ok(Config {
            broker_uri: _config.broker_uri,
            topics: _config.topics,
            client_id: _config.client_id,
            database: _config.database.unwrap_or(DEFAULT_DATABASE.to_string()),
            table: _config.table.unwrap_or(DEFAULT_TABLE.to_string()),
            qos: qos,
        })
    }

    pub fn read() -> Result<Config, String> {
        let config_file = env::var(CONFIG_KEY).unwrap_or(DEFAULT_CONFIG_FILE.to_string());
        Config::read_from_file(&config_file)
    }
}

pub struct Co2db {
    pub connection: Connection,
    pub table: String,
}

pub enum MoveDB {
    APPEND,
    OVERWRITE,
}

impl Co2db {
    pub fn get_schema(table: &str) -> String {
        format!(
            "CREATE TABLE IF NOT EXISTS {} (
                timestamp INTEGER PRIMARY KEY,
                topic TEXT,
                payload TEXT
            );",
            table,
        )
    }

    pub fn new(database: &str, table: &str) -> Result<Co2db, rusqlite::Error> {
        let sql: String = Co2db::get_schema(table);
        let connection = Connection::open(database)?;
        connection.execute(&sql, [])?;
        Ok(Co2db {
            connection,
            table: table.to_string(),
        })
    }

    pub fn new_with_connection(
        connection: Connection,
        table: &str,
    ) -> Result<Co2db, rusqlite::Error> {
        let sql: String = Co2db::get_schema(table);
        connection.execute(&sql, [])?;
        Ok(Co2db {
            connection,
            table: table.to_string(),
        })
    }

    pub fn earliest_datetime(&self) -> Result<DateTime<Utc>, String> {
        let unixtime_ns: i64 = match self.connection.query_row(
            &format!("SELECT min(timestamp) FROM {}", self.table),
            [],
            |row| row.get(0),
        ) {
            Ok(t) => t,
            Err(_e) => return Err("cannot query earliest timestamp".to_string()),
        };
        let seconds = unixtime_ns / 1000000000 as i64;
        let nano = (unixtime_ns % 1000000000) as u32;
        let unixtime: DateTime<Utc> = Utc.timestamp(seconds, nano);

        Ok(unixtime)
    }

    pub fn latest_datetime(&self) -> Result<DateTime<Utc>, String> {
        let unixtime_ns: i64 = match self.connection.query_row(
            &format!("SELECT max(timestamp) FROM {}", self.table),
            [],
            |row| row.get(0),
        ) {
            Ok(t) => t,
            Err(_e) => return Err("cannot query latest timestamp".to_string()),
        };
        let seconds = unixtime_ns / 1000000000 as i64;
        let nano = (unixtime_ns % 1000000000) as u32;
        let unixtime: DateTime<Utc> = Utc.timestamp(seconds, nano);

        Ok(unixtime)
    }

    pub fn count_rows(&self) -> Result<i64, String> {
        let sql: String = format!("SELECT count(*) FROM {}", self.table);
        match self.connection.query_row(&sql, [], |row| row.get(0)) {
            Ok(c) => Ok(c),
            Err(_e) => Err("cannot count rows".to_string()),
        }
    }

    pub fn leave_rows(self: &Self, days: u32) -> Result<(), String> {
        log::debug!("leave_rows days:{}", days);

        let latest_unixtime = self.latest_datetime()?;
        let leave_rows_starting_unixtime = latest_unixtime - Duration::days(days as i64);
        let leave_rows_starting_unixtime_str =
            leave_rows_starting_unixtime.format("%s%f").to_string();
        let sql = format!(
            "DELETE FROM {} WHERE timestamp < {}",
            self.table, leave_rows_starting_unixtime_str
        );
        match self.connection.execute(&sql, []) {
            Ok(_) => Ok(()),
            Err(e) => Err(format!("cannot delete rows: {}", e)),
        }
    }

    pub fn insert(self: &Self, topic: &str, payload: &str) -> Result<(), String> {
        let timestamp: i64 = Utc::now().format("%s%f").to_string().parse().unwrap();
        let sql = format!(
            "INSERT INTO {} (timestamp, topic, payload) VALUES (?1, ?2, ?3)",
            self.table
        );
        match self
            .connection
            .execute(&sql, params![timestamp, topic, payload])
        {
            Ok(_) => Ok(()),
            Err(e) => Err(format!("cannot insert a row: {}", e)),
        }
    }

    pub fn move_db(self: &Self, to_file: &str, opt: MoveDB) -> Result<(), rusqlite::Error> {
        match opt {
            MoveDB::OVERWRITE => {
                if Path::new(to_file).exists() {
                    fs::remove_file(to_file).unwrap();
                }
            }
            MoveDB::APPEND => (),
        }

        let sql: String = Co2db::get_schema(&self.table);
        let to_db = Connection::open(to_file)?;
        to_db.execute(&sql, [])?;

        let sql: String = format!(
            "ATTACH '{}' as to_db;
             INSERT INTO to_db.{} SELECT * FROM {};
             DETACH DATABASE to_db;
             DELETE FROM {};
             VACUUM;",
            to_file, self.table, self.table, self.table
        );
        self.connection.execute_batch(&sql)?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;

    #[test]
    fn when_read_config() {
        let filename = "tests/test_config.json";
        let config = Config::read_from_file(filename).unwrap();
        assert_eq!(config.broker_uri, "broker_uri");
        assert_eq!(config.client_id, "client_id");
        assert_eq!(config.database, "database");
        assert_eq!(config.table, "co2measurement");
        assert_eq!(config.topics, ["topic1", "topic2"]);
        assert_eq!(config.qos, [1, 2]);
    }

    #[test]
    fn when_cant_read_config_file() {
        let filename = "tests/xconfig.json";
        let config = Config::read_from_file(filename);
        assert!(config.is_err());
    }

    #[test]
    fn when_no_filename() {
        env::set_var(CONFIG_KEY, "");
        assert!(Config::read().is_err());
    }

    #[test]
    fn when_set_envrionment_variable() {
        env::set_var(CONFIG_KEY, "tests/test_config.json");
        let config = Config::read().unwrap();
        assert_eq!(config.broker_uri, "broker_uri");
        assert_eq!(config.client_id, "client_id");
        assert_eq!(config.database, "database");
        assert_eq!(config.table, "co2measurement");
        assert_eq!(config.topics, ["topic1", "topic2"]);
        assert_eq!(config.qos, [1, 2]);
    }

    #[test]
    fn when_no_topic() {
        let filename = "tests/test_config_without_requirements.json";
        let config = Config::read_from_file(filename);
        assert!(config.is_err());
    }

    #[test]
    fn when_no_database_and_table() {
        let filename = "tests/test_config_without_defaults.json";
        let config = Config::read_from_file(filename).unwrap();
        assert_eq!(config.broker_uri, "broker_uri");
        assert_eq!(config.client_id, "client_id");
        assert_eq!(config.database, DEFAULT_DATABASE);
        assert_eq!(config.table, DEFAULT_TABLE);
        assert_eq!(config.topics, ["topic1", "topic2"]);
        assert_eq!(config.qos, [1, 1]);
    }

    #[test]
    fn ignore_unknown_key() {
        let filename = "tests/test_config_with_unknown_key.json";
        let config = Config::read_from_file(filename).unwrap();
        assert_eq!(config.broker_uri, "broker_uri");
        assert_eq!(config.client_id, "client_id");
        assert_eq!(config.database, "database");
        assert_eq!(config.table, "co2measurement");
        assert_eq!(config.topics, ["topic"]);
    }

    const TEST_NEW_DATABASE: &str = "tests/test_new.db";
    const TEST_INSERT_DATABASE: &str = "tests/test_insert.db";
    const TEST_LEAVE_DATABASE: &str = "tests/test_leave.db";
    const TEST_TABLE: &str = "test_table";
    const TEST_TOPIC: &str = "test_topic";
    const TEST_ORIGINAL_DATABASE: &str = "tests/test_orig.db";
    const TEST_ORIGINAL_DATABASE_ROWS: i64 = 19161;
    const TEST_ORIGINAL_DATABASE_EARLIEST_DATE: &str = "2021-03-18 04:25:49.333282765 UTC";
    const TEST_ORIGINAL_DATABASE_LATEST_DATE: &str = "2021-03-31 12:06:47.440059540 UTC";
    const TEST_ORIGINAL_DATABASE_TOPIC: &str = "measurement";

    #[test]
    fn co2db_new() {
        // db not exists
        if Path::new(TEST_NEW_DATABASE).exists() {
            fs::remove_file(TEST_NEW_DATABASE).unwrap();
        }
        {
            let db = Co2db::new(TEST_NEW_DATABASE, TEST_TABLE).unwrap();
            assert_eq!(db.table, TEST_TABLE.to_string());
        }

        // db exists
        {
            let db = Co2db::new(TEST_NEW_DATABASE, TEST_TABLE).unwrap();
            assert_eq!(db.table, TEST_TABLE.to_string());
        }

        // clean up
        if Path::new(TEST_NEW_DATABASE).exists() {
            fs::remove_file(TEST_NEW_DATABASE).unwrap();
        }
    }

    #[test]
    fn co2db_insert() {
        if Path::new(TEST_INSERT_DATABASE).exists() {
            fs::remove_file(TEST_INSERT_DATABASE).unwrap();
        }

        let start_timestamp: i64 = Utc::now().format("%s%f").to_string().parse().unwrap();

        let db = Co2db::new(TEST_INSERT_DATABASE, TEST_TABLE).unwrap();
        for count in 1..100 {
            db.insert(TEST_TOPIC, &format!("{} 2.0 -3", count)).unwrap();
        }

        let end_timestamp: i64 = Utc::now().format("%s%f").to_string().parse().unwrap();

        struct TestRow {
            timestamp: i64,
            topic: String,
            payload: String,
        }
        let result: TestRow = db
            .connection
            .query_row(
                &format!("SELECT *, max(timestamp) FROM {}", db.table),
                [],
                |row| {
                    Ok(TestRow {
                        timestamp: row.get(0)?,
                        topic: row.get(1)?,
                        payload: row.get(2)?,
                    })
                },
            )
            .unwrap();
        assert!(result.timestamp > start_timestamp);
        assert!(result.timestamp < end_timestamp);
        assert_eq!(result.topic, TEST_TOPIC);
        assert_eq!(result.payload, "99 2.0 -3".to_string());

        if Path::new(TEST_INSERT_DATABASE).exists() {
            fs::remove_file(TEST_INSERT_DATABASE).unwrap();
        }
    }

    #[test]
    fn co2db_count_rows() {
        let db = Co2db::new(TEST_ORIGINAL_DATABASE, TEST_ORIGINAL_DATABASE_TOPIC).unwrap();
        assert_eq!(db.count_rows().unwrap(), TEST_ORIGINAL_DATABASE_ROWS);
    }

    #[test]
    fn co2db_earliest_datetime() {
        let db = Co2db::new(TEST_ORIGINAL_DATABASE, TEST_ORIGINAL_DATABASE_TOPIC).unwrap();
        assert_eq!(
            db.earliest_datetime().unwrap().to_string(),
            TEST_ORIGINAL_DATABASE_EARLIEST_DATE.to_string()
        );
    }

    #[test]
    fn co2db_latest_datetime() {
        let db = Co2db::new(TEST_ORIGINAL_DATABASE, TEST_ORIGINAL_DATABASE_TOPIC).unwrap();
        assert_eq!(
            db.latest_datetime().unwrap().to_string(),
            TEST_ORIGINAL_DATABASE_LATEST_DATE.to_string()
        );
    }

    #[test]
    fn co2db_leave_rows() {
        if Path::new(TEST_LEAVE_DATABASE).exists() {
            fs::remove_file(TEST_LEAVE_DATABASE).unwrap();
        }
        fs::copy(TEST_ORIGINAL_DATABASE, TEST_LEAVE_DATABASE).unwrap();

        let db = Co2db::new(TEST_LEAVE_DATABASE, TEST_ORIGINAL_DATABASE_TOPIC).unwrap();
        db.leave_rows(2).unwrap();
        assert_eq!(db.count_rows().unwrap(), 2877);
        db.leave_rows(1).unwrap();
        assert_eq!(db.count_rows().unwrap(), 1439);

        if Path::new(TEST_LEAVE_DATABASE).exists() {
            fs::remove_file(TEST_LEAVE_DATABASE).unwrap();
        }
    }

    const TEST_DATABASE_FROM: &str = "tests/test_move_database_from.db";
    const TEST_DATABASE_TO: &str = "tests/test_move_database_to.db";
    const TEST_MOVE_TABLE: &str = "move_database_table";
    const TEST_MOVE_TOPIC: &str = "move_database_topic";
    const TEST_MOVE_COUNT: i64 = 100;

    fn create_dummy_database(filename: &str, table: &str, num: i64) -> Co2db {
        if Path::new(filename).exists() {
            fs::remove_file(filename).unwrap();
        }
        let db = Co2db::new(filename, table).unwrap();
        for count in 0..num {
            db.insert(TEST_MOVE_TOPIC, &format!("{} 3.14 -273", count))
                .unwrap();
        }
        db
    }

    #[test]
    fn move_database_file() {
        // move database  with MoveDB::OVERWRITE (create new destination database)
        let from_db = create_dummy_database(TEST_DATABASE_FROM, TEST_MOVE_TABLE, TEST_MOVE_COUNT);

        if Path::new(TEST_DATABASE_TO).exists() {
            fs::remove_file(TEST_DATABASE_TO).unwrap();
        }
        from_db
            .move_db(TEST_DATABASE_TO, MoveDB::OVERWRITE)
            .unwrap();

        // check result
        assert_eq!(from_db.count_rows().unwrap(), 0);

        let sql: String = format!("SELECT COUNT(*) FROM {}", TEST_MOVE_TABLE,);
        let to_db = Connection::open(TEST_DATABASE_TO).unwrap();
        let count: i64 = to_db.query_row(&sql, [], |row| row.get(0)).unwrap();
        assert_eq!(count, TEST_MOVE_COUNT);

        // move database with MoveDB::APPEND (create new destination database)
        let from_db = create_dummy_database(TEST_DATABASE_FROM, TEST_MOVE_TABLE, TEST_MOVE_COUNT);

        if Path::new(TEST_DATABASE_TO).exists() {
            fs::remove_file(TEST_DATABASE_TO).unwrap();
        }
        from_db.move_db(TEST_DATABASE_TO, MoveDB::APPEND).unwrap();

        // check result
        assert_eq!(from_db.count_rows().unwrap(), 0);

        let sql: String = format!("SELECT COUNT(*) FROM {}", TEST_MOVE_TABLE,);
        let to_db = Connection::open(TEST_DATABASE_TO).unwrap();
        let count: i64 = to_db.query_row(&sql, [], |row| row.get(0)).unwrap();
        assert_eq!(count, TEST_MOVE_COUNT);

        // move database (overwrite data to previous database)
        let from_db = create_dummy_database(TEST_DATABASE_FROM, TEST_MOVE_TABLE, TEST_MOVE_COUNT);

        assert!(Path::new(TEST_DATABASE_TO).exists());
        from_db
            .move_db(TEST_DATABASE_TO, MoveDB::OVERWRITE)
            .unwrap();

        // check result
        assert_eq!(from_db.count_rows().unwrap(), 0);

        let sql: String = format!("SELECT COUNT(*) FROM {}", TEST_MOVE_TABLE,);
        let to_db = Connection::open(TEST_DATABASE_TO).unwrap();
        let count: i64 = to_db.query_row(&sql, [], |row| row.get(0)).unwrap();
        assert_eq!(count, TEST_MOVE_COUNT);

        // move database (append data to previous database)
        let from_db = create_dummy_database(TEST_DATABASE_FROM, TEST_MOVE_TABLE, TEST_MOVE_COUNT);

        assert!(Path::new(TEST_DATABASE_TO).exists());
        from_db.move_db(TEST_DATABASE_TO, MoveDB::APPEND).unwrap();

        // check result
        assert_eq!(from_db.count_rows().unwrap(), 0);

        let sql: String = format!("SELECT COUNT(*) FROM {}", TEST_MOVE_TABLE,);
        let to_db = Connection::open(TEST_DATABASE_TO).unwrap();
        let count: i64 = to_db.query_row(&sql, [], |row| row.get(0)).unwrap();
        assert_eq!(count, TEST_MOVE_COUNT * 2);

        // clean up
        if Path::new(TEST_DATABASE_FROM).exists() {
            fs::remove_file(TEST_DATABASE_FROM).unwrap();
        }
        if Path::new(TEST_DATABASE_TO).exists() {
            fs::remove_file(TEST_DATABASE_TO).unwrap();
        }
    }
}
