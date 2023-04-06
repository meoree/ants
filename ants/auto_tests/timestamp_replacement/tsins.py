#!/usr/bin/env -B python3
# -*- coding: utf-8 -*-
import logging
import re
import time
from pathlib import Path
from pprint import pprint
from sys import argv
import socket

import paramiko
import pexpect
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.logging import RichHandler

from ants.auto_tests.connection import BaseSSHParamiko, SFTPParamiko

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_home = Path(Path.home(), 'python', 'auto_network_test_system')

path_test = Path(path_home, 'ants', 'tests', 'timestamp_replacement')
path_connection = Path(path_home, 'data', 'connection_data')
path_commands = Path(path_home, 'ants', 'auto_tests', 'timestamp_replacement', 'commands')
path_test_network = Path(path_home, 'data', 'network_test_configs')


def timestamp_test_start(tsins_device_dict, tsins_network_params):
    with open(f"{path_connection}/devices.yaml") as file:
        devices = yaml.safe_load(file)

    rpi_src = tsins_device_dict["rpi"][0]
    rpi_dst = tsins_device_dict["rpi"][1]

    # configure_ssfp(devices, "ssfp1_commands.txt", tsins_device_dict["ssfp"][0])
    # configure_ssfp(devices, "ssfp2_commands.txt", tsins_device_dict["ssfp"][1])
    print(tsins_network_params)
    # mac_src = get_rpi_settings_for_script(devices, rpi_src)
    # mac_dst = get_rpi_settings_for_script(devices, rpi_dst)
    ip_src = tsins_network_params[rpi_src]["ip"]
    ip_dst = tsins_network_params[rpi_dst]["ip"]
    intf_src = tsins_network_params[rpi_src]["interface"]
    vlan_src = tsins_network_params[rpi_src]["vlan"]

    print(ip_src, vlan_src, ip_dst, intf_src)
    # 10.3.50.102 10.3.50.103 550 eth0
    # все данные есть, далее отправим скрипт на rpi, потом на dst rpi включаем захват пакетов, потом отправим скрипт на src rpi

    script_path = Path(path_test, 'pattern_ssfp.py')
    send_script_to_rpi(devices, script_path, rpi_src)


def send_script_to_rpi(devices, local_path, rpi):
    try:
        remote_path = "tests/"
        with SFTPParamiko(**devices[rpi]) as sftp:
            print(sftp.check_dir(remote_path))
            sftp.mkdir(f"{remote_path}/tsins")
           # sftp.put_file(local_path, remote_path)
    except (FileNotFoundError, FileExistsError) as error:
        logging.error(f"An error occurred while working with the file '{local_path}' - {error}")
    except OSError as error:
        logging.error(f"An error has occurred on the device {rpi} - {error}")


def configure_ssfp(devices, file, ssfp):
    try:
        with open(f"{path_commands}/{file}") as file:
            ssfp1_commands = file.read().split('\n')
        with BaseSSHParamiko(**devices[ssfp]) as ssh:
            output = ssh.send_shell_show_commands(ssfp1_commands, print_output=True)
        return output
    except (FileNotFoundError, FileExistsError) as error:
        logging.error(f"An error occurred while working with the file '{file}' - {error}")
    except OSError as error:
        logging.error(f"An error has occurred on the device {ssh.ip} - {error}")


def get_rpi_settings_for_script(devices, rpi, vlan=550):
    try:
        with BaseSSHParamiko(**devices[rpi]) as ssh:
            output = ssh.send_exec_commands("ip a")
            match = re.search(rf"\w+.{vlan}.+link/ether\s+(?P<mac>\S+)", output, re.DOTALL)
            if match:
                return match.group('mac')
            else:
                logging.error(f"The subinterface is not configured on the device {ssh.ip}")
    except socket.timeout as error:
        logging.error(f"An error has occurred on the device - {error}")


if __name__ == "__main__":
    tsins_device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi": ["rpi2", "rpi3"],
    }
    print(Path.home())
    # должен передавать ci-cd
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)
    timestamp_test_start(tsins_device_dict, network_params)
