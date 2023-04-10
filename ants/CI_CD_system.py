#!/usr/bin/env -B python3
# -*- coding: utf-8 -*-
import logging
import re
import socket
import time
from pathlib import Path
from pprint import pprint
from sys import argv
import sys

import paramiko
import pexpect
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.logging import RichHandler

from auto_tests.connection import BaseSSHParamiko, SFTPParamiko, ScanDevices
from  auto_tests.timestamp_replacement.tsins import timestamp_test

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)


path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_default = Path(path_home, 'data', 'default_configs')
path_test = Path(path_home, 'ants', 'tests', 'timestamp_replacement')
path_connection = Path(path_home, 'data', 'connection_data')
path_commands = Path(path_home, 'ants', 'auto_tests', 'timestamp_replacement', 'commands')
path_test_network = Path(path_home, 'data', 'network_test_configs')


# -----------------------------Adding Subinterfaces----------------------------#
def template_network_config_file(device):
    env = Environment(loader=FileSystemLoader(path_config), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("change_net_config_file.txt")
    return template.render(device)


def check_network_config_file(network_params, content):
    logging.info("Проверка сетевых интерфейсов устройства")

    intf_vlan_content = re.findall(r'auto (\S+\d)\.(\d+)', content)
    ip_content = re.findall(r"address (\S+)", content)

    intf_vlan_network = (network_params["interface"], f"{network_params['vlan']}")
    ip_network = network_params["ip"]

    if ip_network in ip_content:
        logging.error(f"IP-адрес {ip_network} уже настроен на устройстве")
    elif intf_vlan_network in intf_vlan_content:
        logging.error(f"Подинтерфейс {intf_vlan_network} уже настроен на устройстве")
    else:
        logging.info(f"IP-адрес {ip_network} и подинтерфейс {intf_vlan_network} свободны")
        template_network_config = template_network_config_file(network_params)
        return template_network_config
    return False


def setup_network_config_file(ssh, sftp, network_params_for_test):
    file_path = network_params_for_test["path"]
    file_content = sftp.read_file(file_path)
    template = check_network_config_file(network_params_for_test, file_content)
    if template:
        logging.info("Настройка подинтерфейса на устройстве")
        sftp.add_to_file(template, file_path)
        ssh.send_exec_commands("sudo systemctl restart networking.service")


# -----------------------------Сброс файла в дефолт----------------------------#
def default_template_network_config_file(management_device):
    env = Environment(loader=FileSystemLoader(path_default), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("rpi_config_template.txt")
    return template.render(management_device)


def default_network_config_file(ssh_client, sftp_client, mngmt_params, file_path):
    content = default_template_network_config_file(mngmt_params)
    sftp_client.overwrite_file(content, file_path)
    ssh_client.send_exec_commands("sudo systemctl restart networking.service")


if __name__ == "__main__":
    with open(f"{path_connection}/devices.yaml") as file:
        devices = yaml.safe_load(file)
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)

    tsins_device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi": ["rpi2", "rpi3"],
    }
    logging.info("Checking the availability of devices selected for the test")
    scan_tsins_test = ScanDevices(devices, tsins_device_dict)
    _, fail = scan_tsins_test.scan_devices()
    if fail:
        sys.exit(f"There are devices to which it was not possible to connect - {fail}"
                 f"\nCannot run test.")
    logging.info("TEST TIMESTAMP REPLACE")
    #timestamp_test(devices, tsins_device_dict, network_params)
