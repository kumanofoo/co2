use clap::{App, Arg};
use co2db;
use rusqlite::Result;
use std::{env, ffi::OsStr, ffi::OsString, fs, path::PathBuf, process};

#[derive(PartialEq, Debug)]
enum ARGUMENT {
    KEEP(u32),
    ROTATE(u32),
    TIMESTAMP,
    NONE,
}

fn parse_args<I, T>(args: I) -> Result<ARGUMENT, String>
where
    I: IntoIterator<Item = T>,
    T: Into<OsString> + Clone,
{
    let app = App::new("dbrot")
        .version(env!("CARGO_PKG_VERSION"))
        .author(env!("CARGO_PKG_AUTHORS"))
        .about("rotation log in sqlite3")
        .arg(
            Arg::with_name("keep")
                .help("Keep log days, months or years.\nFor example, 7d, 1m(60 days) or 2y.")
                .short("k")
                .long("keep")
                .takes_value(true)
                .value_name("time_spec"),
        )
        .arg(
            Arg::with_name("rotate")
                .help("Number of log files shoud be kept.")
                .short("r")
                .long("rotate")
                .takes_value(true)
                .value_name("rotate"),
        )
        .arg(
            Arg::with_name("timestamp")
                .help("Display earliest and latest timestamp")
                .short("t")
                .long("timestamp"),
        );
    let matches = match app.get_matches_from_safe(args) {
        Ok(matches) => matches,
        Err(e) => return Err(e.message),
    };
    if matches.is_present("timestamp") {
        return Ok(ARGUMENT::TIMESTAMP);
    }

    match (matches.value_of("keep"), matches.value_of("rotate")) {
        (Some(_), Some(_)) => {
            return Err("cannot use 'keep' and 'rotate' at the same time.".to_string())
        }
        (_, _) => (),
    }

    if let Some(time_spec) = matches.value_of("keep") {
        if let Ok(days) = time_spec.parse::<u32>() {
            // integer days without time unit
            return Ok(ARGUMENT::KEEP(days));
        } else {
            // integer days with time unit
            let time_spec_int = &time_spec[..time_spec.len() - 1];
            let days = match time_spec_int.parse::<u32>() {
                Ok(num) => num,
                Err(e) => return Err(e.to_string()),
            };
            let unit = match &time_spec[time_spec.len() - 1..] {
                "d" => 1,
                "w" => 7,
                "m" => 30,
                "y" => 365,
                _ => return Err(String::from("cannot parse argument of unit")),
            };
            return Ok(ARGUMENT::KEEP(days * unit));
        }
    }

    if let Some(rotate) = matches.value_of("rotate") {
        match rotate.parse::<u32>() {
            Ok(n) => return Ok(ARGUMENT::ROTATE(n)),
            Err(e) => return Err(e.to_string()),
        }
    }

    Ok(ARGUMENT::NONE)
}

fn display_datetime(db: &co2db::Co2db) {
    let earliest = db.earliest_datetime().unwrap();
    let latest = db.latest_datetime().unwrap();
    println!("{}", earliest);
    println!("{}", latest);
}

pub fn rotate_file(file_path: &str, table: &str, max_number: i64) {
    let db = co2db::Co2db::new(file_path, table).unwrap();

    let stem = PathBuf::from(file_path);
    let stem = stem.file_stem().unwrap();
    let stem = stem.to_str().unwrap();
    let ext = PathBuf::from(file_path);
    let ext = ext.extension().unwrap_or(OsStr::new(""));
    let ext = ext.to_str().unwrap();

    for i in (1..max_number).rev() {
        let mut old_file = PathBuf::from(file_path);
        old_file.set_file_name(format!("{}{}", stem, i));
        old_file.set_extension(ext);
        if !old_file.exists() {
            continue;
        }

        let mut dest = PathBuf::from(file_path);
        dest.set_file_name(format!("{}{}", stem, i + 1));
        dest.set_extension(ext);
        let _ = fs::rename(old_file, dest).unwrap();
    }

    let mut dest = PathBuf::from(file_path);
    dest.set_file_name(format!("{}1", stem));
    dest.set_extension(ext);
    db.move_db(dest.to_str().unwrap(), co2db::MoveDB::OVERWRITE)
        .unwrap();
}

fn main() {
    env_logger::init();

    let args: Vec<String> = env::args().collect();
    let argument = parse_args(args).unwrap_or_else(|e| {
        eprintln!("{}", e);
        process::exit(0)
    });

    let config = match co2db::Config::read_dbinfo() {
        Ok(conf) => conf,
        Err(e) => {
            eprintln!("configuration error: {}", e);
            process::exit(0);
        }
    };

    log::info!("Database: {:#?}", config.database);
    let db = co2db::Co2db::new(&config.database, &config.table).unwrap();

    match argument {
        ARGUMENT::KEEP(days) => {
            db.leave_rows(days).unwrap_or_else(|e| panic!("{}", e));
        }
        ARGUMENT::TIMESTAMP => {
            display_datetime(&db);
        }
        ARGUMENT::ROTATE(rotate) => {
            rotate_file(&config.database, &config.table, rotate as i64);
        }
        ARGUMENT::NONE => (),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use co2db::Co2db;
    use rusqlite::Connection;
    use std::{fs, path::Path};

    #[test]
    fn parse_test() {
        let args: Vec<&str> = vec!["dbrot", "-k", "3"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(3)));
        let args: Vec<&str> = vec!["dbrot", "-k", "3d"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(3)));
        let args: Vec<&str> = vec!["dbrot", "-k", "3w"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(21)));
        let args: Vec<&str> = vec!["dbrot", "-k", "3m"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(90)));
        let args: Vec<&str> = vec!["dbrot", "-k", "3y"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(3 * 365)));
        let args: Vec<&str> = vec!["dbrot", "--keep", "3"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(3)));
        let args: Vec<&str> = vec!["dbrot", "--keep", "3d"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(3)));
        let args: Vec<&str> = vec!["dbrot", "--keep", "3w"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(21)));
        let args: Vec<&str> = vec!["dbrot", "--keep", "3m"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(90)));
        let args: Vec<&str> = vec!["dbrot", "--keep", "3y"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::KEEP(3 * 365)));

        let args: Vec<&str> = vec!["dbrot", "-r", "3"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::ROTATE(3)));
        let args: Vec<&str> = vec!["dbrot", "--rotate", "3"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::ROTATE(3)));
    }

    #[test]
    fn error_parse() {
        let usage = format!("dbrot {}\n{}\nrotation log in sqlite3\n\nUSAGE:\n    dbrot [FLAGS] [OPTIONS]\n\nFLAGS:\n    -h, --help         Prints help information\n    -t, --timestamp    Display earliest and latest timestamp\n    -V, --version      Prints version information\n\nOPTIONS:\n    -k, --keep <time_spec>    Keep log days, months or years.\n                              For example, 7d, 1m(60 days) or 2y.\n    -r, --rotate <rotate>     Number of log files shoud be kept.",
                            env!("CARGO_PKG_VERSION"),
                            env!("CARGO_PKG_AUTHORS"));
        let args: Vec<&str> = vec!["dbrot"];
        assert_eq!(parse_args(args), Ok(ARGUMENT::NONE));

        let args: Vec<&str> = vec!["dbrot", "-h"];
        assert_eq!(parse_args(args), Err(usage));

        let usage = "\u{1b}[1;31merror:\u{1b}[0m Found argument \'\u{1b}[33m-a\u{1b}[0m\' which wasn\'t expected, or isn\'t valid in this context\n\nUSAGE:\n    dbrot [FLAGS] [OPTIONS]\n\nFor more information try \u{1b}[32m--help\u{1b}[0m".to_string();
        let args: Vec<&str> = vec!["dbrot", "-a"];
        assert_eq!(parse_args(args), Err(usage));

        let args: Vec<&str> = vec!["dbrot", "-k", "10.0"];
        assert!(parse_args(args).is_err());

        let args: Vec<&str> = vec!["dbrot", "--keep", "10x"];
        assert_eq!(
            parse_args(args),
            Err("cannot parse argument of unit".to_string())
        );

        let args: Vec<&str> = vec!["dbrot", "-r", "10x"];
        assert!(parse_args(args).is_err());
        let args: Vec<&str> = vec!["dbrot", "--rotate", "10.0"];
        assert!(parse_args(args).is_err());
    }

    const TEST_ROTATE_FILE: &str = "tests/test_rotate.db";
    const TEST_ROTATE_TABLE: &str = "test_rotate_table";
    const TEST_ROTATE_TOPIC: &str = "test_rotate_topic";
    const TEST_MAX_ROTATE_FILES: i64 = 15;
    const TEST_ROTATE_COUNT: i64 = 100;
    #[test]
    fn rotate_database_file() {
        let stem = PathBuf::from(TEST_ROTATE_FILE);
        let stem = stem.file_stem().unwrap();
        let stem = stem.to_str().unwrap();
        let ext = PathBuf::from(TEST_ROTATE_FILE);
        let ext = ext.extension().unwrap_or(OsStr::new(""));
        let ext = ext.to_str().unwrap();

        // clear all test files
        if Path::new(TEST_ROTATE_FILE).exists() {
            fs::remove_file(TEST_ROTATE_FILE).unwrap();
        }
        for n in 1..TEST_MAX_ROTATE_FILES + 1 {
            let mut rotate_file = PathBuf::from(TEST_ROTATE_FILE);
            rotate_file.set_file_name(format!("{}{}", stem, n));
            rotate_file.set_extension(ext);
            if rotate_file.exists() {
                fs::remove_file(rotate_file).unwrap();
            }
        }

        // run rotate_file()
        let db = Co2db::new(TEST_ROTATE_FILE, TEST_ROTATE_TABLE).unwrap();
        for n in 1..TEST_ROTATE_COUNT + 1 {
            db.insert(TEST_ROTATE_TOPIC, &format!("{}", n)).unwrap();
            rotate_file(TEST_ROTATE_FILE, TEST_ROTATE_TABLE, TEST_MAX_ROTATE_FILES);
        }

        // check results
        let sql: String = format!("SELECT payload FROM {}", TEST_ROTATE_TABLE);
        let conn = Connection::open(TEST_ROTATE_FILE).unwrap();
        let payload: String = conn
            .query_row(&sql, [], |row| row.get(0))
            .unwrap_or("".to_string());
        assert_eq!(payload, "".to_string());

        for n in 1..TEST_MAX_ROTATE_FILES + 1 {
            let mut rotate_file = PathBuf::from(TEST_ROTATE_FILE);
            rotate_file.set_file_name(format!("{}{}", stem, n));
            rotate_file.set_extension(ext);

            let conn = Connection::open(rotate_file).unwrap();
            let payload: String = conn.query_row(&sql, [], |row| row.get(0)).unwrap();
            assert_eq!(payload, (TEST_ROTATE_COUNT + 1 - n).to_string());
        }

        // clear all test files
        if Path::new(TEST_ROTATE_FILE).exists() {
            fs::remove_file(TEST_ROTATE_FILE).unwrap();
        }
        for n in 1..TEST_MAX_ROTATE_FILES + 1 {
            let mut rotate_file = PathBuf::from(TEST_ROTATE_FILE);
            rotate_file.set_file_name(format!("{}{}", stem, n));
            rotate_file.set_extension(ext);
            if rotate_file.exists() {
                fs::remove_file(rotate_file).unwrap();
            }
        }
    }
}
