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

path_test = Path(Path.cwd(), 'ants', 'tests', 'timestamp_replacement')
path_connection = Path(Path.cwd(), 'data', 'connection_data')
path_commands = Path(Path.cwd(), 'ants', 'auto_tests', 'timestamp_replacement', 'commands')     
path_test_network = path_commands = Path(Path.cwd(), 'data', 'network_test_configs')    

def timestamp_test_start(tsins_device_dict, tsins_network_params):
    with open(f"{path_connection}/devices.yaml") as file:
        devices  = yaml.safe_load(file)

    #configure_ssfp(devices, "ssfp1_commands.txt", tsins_device_dict["ssfp"][0])
    #configure_ssfp(devices, "ssfp2_commands.txt", tsins_device_dict["ssfp"][1])

    mac_src = get_rpi_settings_for_script(devices, tsins_device_dict["rpi"][0])
    mac_dst = get_rpi_settings_for_script(devices, tsins_device_dict["rpi"][1])

def configure_ssfp(devices, file, ssfp):
    try:
        with open(f"{path_commands}/{file}") as file:
            ssfp1_commands = file.read().split('\n')
        with BaseSSHParamiko(**devices[ssfp]) as ssh:
            output = ssh.send_shell_show_commands(ssfp1_commands, print_output=True)
        return output
    except (FileNotFoundError,  FileExistsError) as error:
        logging.error(f"An error occurred while working with the file '{file}' - {error}")
    except OSError as error:
        logging.error(f"An error has occurred on the device {ssh.ip} - {error}")

def get_rpi_settings_for_script(devices, rpi):
    try:
        with BaseSSHParamiko(**devices[rpi]) as ssh:
            output = ssh.send_exec_commands("ip a")
    except socket.timeout as error:
         logging.error(f"На устройстве возникла ошибка - {error}")
    match = re.search(r"\w+.550.+link/ether\s+(?P<mac>\S+)", output, re.DOTALL)
    if match:
        return match.group('mac')
    else:
        logging.error(f"The subinterface is not configured on the device {ssh.ip}")

if __name__ == "__main__":
    tsins_device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi" : ["rpi2", "rpi3"], 
    }
    
    #должен передавать ci-cd
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)
    timestamp_test_start(tsins_device_dict, network_params)
 




        
