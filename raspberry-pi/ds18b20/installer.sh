#! /bin/bash

set -ue


bin=ds18b20
binpath=target/release
config_ex=ds18b20.json-example
unitfile=ds18b20_pub.service

prefix=/opt
install_dir=${prefix}/ds18b20_pub

user_id=ds18b20


build() {
    cargo build --release
}

install_ds18b20() {
    install -v -m 755 -d ${install_dir}
    install -v -m 755 -d ${install_dir}/bin
    (cd ${binpath} && install -v -m 755 -t ${install_dir}/bin ${bin})

    if id "${user_id}" &>/dev/null; then
        echo ${user_id} user already exists.
    else
        useradd -d ${install_dir} -s /usr/sbin/nologin -r ${user_id} || exit $?
    fi
    
    install -v -m 644 -t ${install_dir} ${config_ex} ${unitfile}
    chown -R ${user_id}:${user_id} ${install_dir}
    ln -f -s ${install_dir}/${unitfile} /etc/systemd/system
    echo ""
    echo "Start ds18b20_pub service."
    echo "$ sudo systemctl start ds18b20"
    echo ""
    echo "Check ds18b20_pub service."
    echo "$ systemctl status ds18b20"
    echo ""
    echo "Enable to start ds18b20_pub service on system boot."
    echo "$ sudo systemctl enable ds18b20_pub"
    echo ""
}

uninstall_ds18b20() {
    systemctl stop -q ds18b20_pub || true
    systemctl disable -q ds18b20_pub || true
    rm -f /etc/systemd/system/${unitfile}
    rm -f ${install_dir}/${unitfile}

    (
        cd ${install_dir}/bin || exit $?
        rm -f ${bin}
    )
    rmdir ${install_dir}/bin

    (
        cd ${install_dir} || exit $?
        rm -ri *
    )
    if [ "$(ls -A ${install_dir})" ]; then
        echo ${install_dir} has been left because not empty.
    else
        rmdir ${install_dir}
    fi

    userdel ${user_id}
}
    
usage() {
    echo "usage: ${0##*/} [build|install|uninstall]"
}

case "$1" in
    build)
        build
        ;;
    install)
        install_ds18b20
        ;;
    uninstall)
        uninstall_ds18b20
        ;;
    *)
        usage
        ;;
esac

exit 0
