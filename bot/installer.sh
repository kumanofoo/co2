#!/bin/bash

set -e

user_id=monibot
co2group=co2
prefix=/opt
monibotd_dir="${prefix}/monibot"
etc_dir="${monibotd_dir}/etc"

docker_image="monibot:test"
docker_container="test_monibot"

install_monibot() {
    python3 -m venv ${monibotd_dir}
    source ${monibotd_dir}/bin/activate
    pip install wheel
    pip install .[dev]
    install -m 755 -d ${etc_dir}
    install -m 644 monibot-sample.conf ${etc_dir}
    install -m 644 co2plot-sample.json ${etc_dir}

    if [ -f /etc/default/monibot ]; then
        echo skip install /etc/default/monibot
    else
        install -o root -g root -m 600 monibot /etc/default
    fi

    # Slack
    if [ -f /etc/systemd/system/monibotd.service ]; then
        echo skip install /etc/systemd/system/monibotd.service
    else
        install -o root -g root -m 644 \
                monibotd.service \
                /etc/systemd/system
    fi

    # Zulip
    if [ -f /etc/systemd/system/monibotzd.service ]; then
        echo skip install /etc/systemd/system/monibotzd.service
    else
        install -o root -g root -m 644 \
                monibotzd.service \
                /etc/systemd/system
    fi

    if id ${user_id} &>/dev/null; then
        echo ${user_id} user already exists.
    else
        useradd -d ${monibotd_dir} -s /usr/sbin/nologin -r ${user_id} || exit $?
    fi
    groupadd -f ${co2group}
    gpasswd -a ${user_id} ${co2group} &>/dev/null

    # matplotlib cache directory
    install -m 700 -o ${user_id} -g ${co2group} -d ${monibotd_dir}/.config 
    install -m 700 -o ${user_id} -g ${co2group} -d ${monibotd_dir}/.config/matplotlib

    cat <<EOF

Slack bot: monibotd
Zulip bot: monibotzd

Start bot service
$ sodo systemctl start [monibotd or monibotzd]

Check service
$ systemctl status [monibotd or monibotzd]

Enable to start bot service on system boot 
$ sudo systemctl enable [monibotd or monibotzd]

EOF
}

uninstall_monibot() {
    if ! [ -d ${monibotd_dir} ]; then
        echo "${monibotd_dir} does not exist."
        exit 0
    fi

    read -p "Are you sure (yes/NO)? " reply
    case "${reply}" in
        yes)
            ;;
        *)
            echo canceled
            exit 1
            ;;
    esac

    systemctl stop monibotd
    systemctl disable monibotd
    rm /etc/systemd/system/monibotd.service
    rm /etc/systemd/system/monibotzd.service
    rm /etc/default/monibot
    rm -r ${monibotd_dir}

    gpasswd -d ${user_id} ${co2group} &>/dev/null
    userdel ${user_id} &>/dev/null
}

initialize_docker() {
    # build docker image
    (docker image build -t ${docker_image} -f Dockerfile .)

    # run docker container and install monibot
    if [ -f docker/monibot ]; then
        docker run -itd --rm -e TZ=Asia/Tokyo --env-file=docker/monibot --name ${docker_container} ${docker_image}
    else
        docker run -itd --rm -e TZ=Asia/Tokyo --name ${docker_container} ${docker_image}
    fi
    
    # set signal handler
    trap "docker stop ${docker_container}" SIGINT SIGHUP

    # copy monibot files to container
    temp_dir=$(mktemp -d)
    monibot_files=${temp_dir}/files.tar.gz
    tar zcf ${monibot_files} $(git ls-files)
    docker cp ${monibot_files} ${docker_container}:/tmp/
    rm ${monibot_files}
    rmdir ${temp_dir}
    docker exec ${docker_container} /bin/bash \
           -c 'mkdir -p /root/project/monibot && tar zxf /tmp/files.tar.gz -C /root/project/monibot'
    if [ -f docker/measurement.db ];then
        docker cp docker/measurement.db ${docker_container}:/var/log/
    fi

    # exec installer in container
    docker exec ${docker_container} /bin/bash -c "cd monibot && /bin/bash installer.sh install"

    # copy config files to container
    if [ -f docker/monibot.conf ]; then
        docker cp docker/monibot.conf ${docker_container}:${etc_dir}
        docker exec ${docker_container} /bin/bash -c "chmod 644 ${etc_dir}/monibot.conf"
    fi
    if [ -f docker/co2plot.json ]; then
        docker cp docker/co2plot.json ${docker_container}:${etc_dir}
        docker exec ${docker_container} /bin/bash -c "chmod 644 ${etc_dir}/co2plot.json"
    fi
}

test_on_docker() {
    initialize_docker
    # run test
    docker exec ${docker_container} /bin/bash -c 'source /opt/monibot/bin/activate && cd monibot && pytest'
    stop_docker
}

slack_on_docker() {
    initialize_docker
    # run monibotd
    docker exec ${docker_container} /bin/bash -c 'source /opt/monibot/bin/activate && monibot'
    stop_docker
}

zulip_on_docker() {
    initialize_docker
    # run monibotd
    docker exec ${docker_container} /bin/bash -c 'source /opt/monibot/bin/activate && monibotz'
    stop_docker
}

stop_docker() {
    container=$(docker ps | grep -c 'test_monibot')
    if [ $container = 1 ]; then
        docker stop ${docker_container}
    fi
}

usage() {
    echo "usage: ${0##*/} [install|uninstall|test-docker|slack-docker|zulip-docker|stop-docker]"
}

case "$1" in
    install)
        install_monibot
        ;;
    uninstall)
        uninstall_monibot
        ;;
    test-docker)
        test_on_docker
        ;;
    slack-docker)
        slack_on_docker
        ;;
    zulip-docker)
        zulip_on_docker
        ;;
    stop-docker)
        stop_docker
        ;;
    *)
        usage
        ;;
esac

exit 0
