#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import pexpect
import paramiko
import re
import yaml
import logging
import time
import logging
import socket
from pathlib import Path
from sys import argv
from rich.logging import RichHandler
from jinja2 import Environment, FileSystemLoader
from pprint import pprint

from auto_tests.connection import BaseSSHParamiko
from auto_tests.timestamp_replacement.pattern_ssfp import timestamp_test_start


logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_test = Path(Path.cwd(), 'ants', 'tests', 'timestamp_replacement')
path_config = Path(Path.cwd(), 'data', 'network_test_configs')
path_connection = Path(Path.cwd(), 'data', 'connection_data')
path_default = Path(Path.cwd(), 'data', 'default_configs')

#-----------------------------Добавление подинтерфейсов----------------------------#
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

def setup_network_config_file(cl_SSH, cl_SFTP, network_params_for_test):
    file_path = network_params_for_test["path"]
    file_content = cl_SFTP.read_file(file_path)
    template = check_network_config_file(network_params_for_test, file_content)
    if template:
        logging.info("Настройка подинтерфейса на устройстве")
        cl_SFTP.add_to_file(template, file_path)
        cl_SSH.send_setup_command("sudo systemctl restart networking.service")

#-----------------------------Сброс файла в дефолт----------------------------#
def default_template_network_config_file(management_device):
    env = Environment(loader=FileSystemLoader(path_default), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("rpi_config_template.txt")
    return template.render(management_device)

def default_network_config_file(ssh_client, sftp_client, mngmt_params, file_path):
    content = default_template_network_config_file(mngmt_params)
    sftp_client.overwrite_file(content, file_path)
    ssh_client.send_setup_command("sudo systemctl restart networking.service")


if __name__ == "__main__":
    device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi" : ["rpi3"]
    }
    device_list = ["ssfp1", "rpi3"]
    print(timestamp_test_start(device_dict))
 

    
    