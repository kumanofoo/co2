target = ds18b20
user_id = $(target)
target_dir = target/release
target_bin = $(target_dir)/$(target)
config_file_orig = ds18b20.json-example
config_file = ds18b20.json

src = src/main.rs src/lib.rs src/ds18b20.rs
cargo = Cargo.toml
install_dir = /opt/ds18b20_pub
systemd_dir = /etc/systemd/system

service_file = ds18b20_pub.service

$(target_bin) : $(src) $(cargo)
	cargo build --release

install : $(target_bin) $(config_file)
	id $(user_id); if [ $$? -ne 0 ]; then useradd $(user_id) -s /usr/sbin/nologin -d $(install_dir); fi
	install -v -m 750 -o $(user_id) -g $(user_id) -d $(install_dir)
	install -v -m 750 -o $(user_id) -g $(user_id) -t $(install_dir) $(target_bin)
	install -v -m 644 -o $(user_id) -g $(user_id) -t $(install_dir) $(config_file_orig)
	install -v -m 644 -t $(systemd_dir) $(service_file)

uninstall :
	systemctl stop ds18b20_pub || true
	rm $(systemd_dir)/$(service_file) || true
	cd $(install_dir); rm $(target) $(config_file_orig) || true
	if [ -f $(install_dir)/$(config_file) ]; then rm -i $(install_dir)/$(config_file); fi
	rmdir $(install_dir) || true
	id $(user_id); if [ $$? -eq 0 ]; then userdel $(user_id); fi
