#!/bin/bash

set -e

monibotd_dir="/opt/monibot"
etc_dir="${monibotd_dir}/etc"

docker_image="monibot:test"
docker_container="test_monibot"

install_monibot() {
    python3 -m venv ${monibotd_dir}
    source ${monibotd_dir}/bin/activate
    pip install wheel
    pip install .[dev]
    install -o root -g root -m 755 -D -d ${etc_dir}
    install -o root -g root -m 644 monibot-sample.conf ${etc_dir}
    install -o root -g root -m 644 co2plot-sample.json ${etc_dir}

    if [ -f /etc/default/monibot ]; then
        echo skip install /etc/default/monibot
    else
        install -o root -g root -m 600 monibot /etc/default
    fi

    if [ -f /etc/systemd/system/monibotd.service ]; then
        echo skip install /etc/systemd/system/monibotd.service
    else
        install -o root -g root -m 644 \
                monibotd.service \
                /etc/systemd/system
    fi


    cat <<EOF

Start monibotd service
$ sodo systemctl start monibotd

Check monibotd service
$ systemctl status monibotd

Enable to start monibotd service on system boot 
$ sudo systemctl enable monibotd

EOF
}

uninstall_monibot() {
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
    rm /etc/default/monibot
    rm -r ${monibotd_dir}
}

initialize_docker() {
    # build docker image
    (docker image build -t ${docker_image} -f Dockerfile .)

    # run docker container and install monibot
    if [ -f docker/monibot ]; then
        docker run -itd --rm --env-file=docker/monibot --name ${docker_container} ${docker_image}
    else
        docker run -itd --rm --name ${docker_container} ${docker_image}
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
    docker exec ${docker_container} /bin/bash -c "cd monibot && /bin/bash install.sh install"

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

run_on_docker() {
    initialize_docker
    # run monibotd
    docker exec ${docker_container} /bin/bash -c 'source /opt/monibot/bin/activate && monibot'
    stop_docker
}

stop_docker() {
    container=$(docker ps | grep -c 'test_monibot')
    if [ $container = 1 ]; then
        docker stop ${docker_container}
    fi
}

usage() {
    echo "usage: ${0##*/} [install|uninstall|test-docker|run-docker|stop-docker]"
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
    run-docker)
        run_on_docker
        ;;
    stop-docker)
        stop_docker
        ;;
    *)
        usage
        ;;
esac

exit 0
