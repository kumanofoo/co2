#!/usr/bin/env bats

sqlite3=/usr/bin/sqlite3
orig_database=tests/test_orig.db
test_database=tests/test.db

setup() {
    cargo build --release --bin dbrot 
    cp ${orig_database} ${test_database}
}

teardown() {
    rm ${test_database}
}

@test "leave log" {
    config=tests/test_dbrot.json
    
    CO2DB_CONFIG=${config} ./target/release/dbrot -k 2
    result=$(sqlite3 tests/test.db "select count(*) from measurement")
    [ "$result" -eq "2877" ]
    
    CO2DB_CONFIG=${config} ./target/release/dbrot -k 1
    result=$(sqlite3 tests/test.db "select count(*) from measurement")
    [ "$result" -eq "1439" ]
}

@test "rotate DB" {
    config=tests/test_dbrot_rotate.json
    
    db=$(grep database ${config} | perl -pe 's/^.+\:\s*\"(.+)\"\s*[,]*$/$1/')
    table=$(grep table ${config} | perl -pe 's/^.+\:\s*\"(.+)\"\s*[,]*$/$1/')
    topic=$(grep topic ${config} | perl -pe 's/^.+\:\s*\"(.+)\"\s*[,]*$/$1/')
    echo "output = ${db}"
    for payload in {1..10}; do
        timestamp=$(perl -MTime::HiRes=gettimeofday -E '($sec, $microsec)=gettimeofday; printf "%d%d", $sec, $microsec')
        sqlite3 ${db} <<EOF
CREATE TABLE IF NOT EXISTS
    ${table} (
        timestamp INTEGER PRIMARY KEY,
        topic TEXT,
        payload TEXT
    )
;
INSERT 
INTO 
    ${table} (
        timestamp,
        topic,
        payload
    )
VALUES (
    '${timestamp}',
    '${topic}',
    '${payload}'
)
;
EOF
        CO2DB_CONFIG=${config} ./target/release/dbrot -r 5
    done
    files=$(ls ${db%.*}?.${db##*.})
    i=10
    for f in $files; do
        result=$(sqlite3 ${f} "select payload from ${table}")
        [ "$result" -eq "$i" ]
        i=$((i-1))
        rm ${f}
    done
    rm ${db}
}
