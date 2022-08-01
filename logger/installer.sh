#! /bin/bash

set -ue


co2user=co2
prefix=/opt
co2dir=${prefix}/co2
co2bin='co2db dbrot'
binpath=target/release
config=co2db.json
config_ex=co2db.json-example
unitfile=co2db.service


build() {
    cargo build --release
}

install_co2() {
    install -v -m 755 -d ${co2dir}
    install -v -m 755 -d ${co2dir}/bin
    (cd ${binpath} && install -v -m 755 -t ${co2dir}/bin ${co2bin})
    install -v -m 644 -t ${co2dir} ${config_ex}

    if id "${co2user}" &>/dev/null; then
	echo $co2user user already exists.
    else
	useradd -d ${co2dir} -s /usr/sbin/nologin -r ${co2user} || exit $?
    fi
    install -v -m 644 -t ${co2dir} ${unitfile}
    chown -R ${co2user}:${co2user} ${co2dir}
    ln -f -s ${co2dir}/${unitfile} /etc/systemd/system
}

uninstall_co2() {
    systemctl stop co2db
    systemctl disable co2db
    rm -f /etc/systemd/system/${unitfile}
    rm -f ${co2dir}/${unitfile}

    (
	cd ${co2dir}/bin || exit $?
	rm -f ${co2bin}
    )
    rmdir ${co2dir}/bin
    
    (
	cd ${co2dir} || exit $?
	rm -ri *
    )
    if [ "$(ls -A ${co2dir})" ]; then
	echo ${co2dir} has been left because not empty.
    else
	rmdir ${co2dir}
    fi

    userdel ${co2user}
}

usage() {
    echo "usage: ${0##*/} [build|install|uninstall]"
}

case "$1" in
    build)
	build
	;;
    install)
	install_co2
	;;
    uninstall)
	uninstall_co2
	;;
    *)
	usage
	;;
esac

exit 0
