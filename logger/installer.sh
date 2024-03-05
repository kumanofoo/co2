#! /bin/bash

set -ue


co2user=co2
prefix=/opt
co2dir=${prefix}/co2
co2bin='co2db dbrot'
restbin='mqtt2rest rest2co2db dbrot'
allbin='co2db mqtt2rest rest2co2db dbrot'
binpath=target/release
if [ ! -d ${binpath} ]; then
    binpath=.
fi
config=co2db.json
config_ex=co2db.json-example
services=./services


build_co2() {
    for t in ${@}; do
        cargo build --release --bin $t
    done
}

install_co2() {
    install -v -m 755 -d ${co2dir}
    install -v -m 755 -d ${co2dir}/bin
    for b in ${allbin}; do
        if [ -f "${binpath}/${b}" ]; then
            (cd ${binpath} && install -v -m 755 -t ${co2dir}/bin ${b})
            echo installing ${b}.

            unitfile="${b}.service"
            if [ -f "${services}/${unitfile}" ]; then
                install -v -m 644 -t ${co2dir} ${services}/${unitfile}
                ln -f -s ${co2dir}/${unitfile} /etc/systemd/system
            fi
        fi
    done
    install -v -m 644 -t ${co2dir} ${config_ex}

    if id "${co2user}" &>/dev/null; then
	$co2user user already exists.
    else
	useradd -d ${co2dir} -s /usr/sbin/nologin -r ${co2user} || exit $?
    fi
    chown -R ${co2user}:${co2user} ${co2dir}
}

uninstall_co2() {
    for b in ${allbin}; do
	unitfile="${b}.service"
	if [ -f "/etc/systemd/system/${unitfile}" ]; then
	    systemctl stop ${b}
	    systemctl disable ${b}
	    rm /etc/systemd/system/${unitfile}
	    rm ${co2dir}/${unitfile} 2> /dev/null || true
	fi
    done

    (
	cd ${co2dir}/bin || exit $?
	rm ${allbin} 2> /dev/null || true
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
    echo "usage: ${0##*/} build [co2db|mqtt2rest|rest2co2db|dbrot|all]"
    echo "       ${0##*/} install"
    echo "       ${0##*/} uninstall"
}

if [ "$#" -eq 0 ]; then
    usage
    exit 0
fi

cmd=$1
bin=${@:2}
if [ "$bin" = "" ] || [ "$bin" = "all" ]; then
    bin=$allbin
fi

case "$cmd" in
    build)
	build_co2 "$bin"
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
