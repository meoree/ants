# -*- coding: utf-8 -*-
""" Tsins test
Testing the tsins function on the M720.
When traffic passes through the M720 in transit, the twins service on two M720 replaces
timestamps instead of patterns in the packet data field.
Packets with patterns are generated on RPi using scapy and sent.
Traffic with timestamps comes to another RPi, where dump is captured.
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path
import socket
import os

import yaml
from rich.logging import RichHandler
from jinja2 import Environment, FileSystemLoader
from ipaddress import IPv4Address, AddressValueError

from ants.connection import BaseSSHParamiko, SFTPParamiko

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_test = Path(path_home, 'ants', 'auto_tests', 'timestamp_replacement')
path_connection = Path(path_home, 'data', 'connection_data')
path_commands = Path(path_home, 'ants', 'auto_tests', 'timestamp_replacement', 'commands')
path_test_network = Path(path_home, 'data', 'network_test_configs')


def timestamp_test(devices, tsins_device_dict, tsins_network_params):
    logging.info("PREPARATION FOR THE TEST")

    try:
        rpi_src = tsins_device_dict["rpi"][0]
        rpi_dst = tsins_device_dict["rpi"][1]
        rpi_ntp = tsins_device_dict["rpi"][2]

        ntp_ip = tsins_network_params["rpi"][rpi_ntp]["ip"]
        ip_src = tsins_network_params["rpi"][rpi_src]["ip"]
        ip_dst = tsins_network_params["rpi"][rpi_dst]["ip"]
        intf_src = tsins_network_params["rpi"][rpi_src]["interface"]
        vlan_src = tsins_network_params["rpi"][rpi_src]["vlan"]
        vlan_dst = tsins_network_params["rpi"][rpi_src]["vlan"]

    except (KeyError, IndexError):
        logging.error("3 RPi and 2 SSFP should be transmitted")
        return False

    try:
        int(vlan_src) + int(vlan_dst)
    except ValueError:
        logging.error("VLAN must be a number in network parameters for test")
        return False

    try:
        IPv4Address(ip_dst)
        IPv4Address(ip_src)
        IPv4Address(ntp_ip)
    except AddressValueError:
        logging.error("Wrong IP address in network parameters for test")
        return False

    if type(intf_src) != str:
        logging.error("Wrong interface in network parameters for test")
        return False

    configure_ssfp(devices, "ssfp1_commands.txt", tsins_device_dict["ssfp"][0], ntp_ip)
    configure_ssfp(devices, "ssfp2_commands.txt", tsins_device_dict["ssfp"][1], ntp_ip)

    mac_src = get_rpi_settings_for_script(devices, rpi_src, vlan_src)
    mac_dst = get_rpi_settings_for_script(devices, rpi_dst, vlan_dst)

    script_path = send_script_to_rpi(devices, 'pattern_ssfp.py', rpi_src)

    with BaseSSHParamiko(**devices[rpi_src]) as cl_src:
        with BaseSSHParamiko(**devices[rpi_dst]) as cl_dst:
            logging.info("TEST STARTED")
            # tcpdump results stored /tests/tsins/
            cl_dst.send_shell_commands(["mkdir tests", "cd tests", "mkdir tsins", "cd tsins"])
            for number_of_test in range(1, 6):
                logging.info(f"Number of test: {number_of_test}")
                output_dst = cl_dst.send_shell_commands(f"tcpdump -i {intf_src}.{vlan_src} -c 1000 -w "
                                                        f"{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}_tsins_{number_of_test}.pcap")
                logging.debug(output_dst)
                time.sleep(3)
                output_src = cl_src.send_shell_commands(f"python3 {script_path} "
                                                        f"{mac_src} {mac_dst} {ip_src} {ip_dst} {intf_src} {vlan_src} {number_of_test}")
                logging.debug(output_src)
                time.sleep(5)
    # Дальше дампы надо отправить на сервер
    logging.info("TEST FINISHED")
    stop_services_ssfp(devices, tsins_device_dict["ssfp"][0])
    stop_services_ssfp(devices, tsins_device_dict["ssfp"][1])
    logging.info("Commands were removed")
    return True


def configure_ssfp(devices, file_with_commands, ssfp, ntp_ip):
    try:
        if os.stat(Path(path_commands, file_with_commands)).st_size == 0:
            logging.info(f"File {file_with_commands} is empty")
            return False
        environment = Environment(loader=FileSystemLoader(path_commands),
                                  trim_blocks=True, lstrip_blocks=True)
        template = environment.get_template(file_with_commands)
        commands = template.render({'ntp_ip': ntp_ip}).split("\n")
        with BaseSSHParamiko(**devices[ssfp]) as ssh:
            output = ssh.send_shell_commands(commands)
            logging.debug(output)
            return output
    except (FileNotFoundError, FileExistsError) as error:
        logging.error(f"An error occurred while working with the file '{file_with_commands}' - {error}")
    except OSError as error:
        logging.error(f"An error has occurred on the device - {error}")
    return False


def stop_services_ssfp(devices, ssfp):
    try:
        with BaseSSHParamiko(**devices[ssfp]) as ssh:
            output = ssh.send_shell_commands(["run-klish", "configure terminal",
                                              "timesync stop profile0",
                                              "tsins stop profile0"])
            logging.debug(output)
    except OSError as error:
        logging.error(f"An error has occurred on the device {ssh.ip} - {error}")


def get_rpi_settings_for_script(devices, rpi, vlan):
    try:
        with BaseSSHParamiko(**devices[rpi]) as ssh:
            output = ssh.send_exec_commands("ip a")
            match = re.search(rf"\w+.{vlan}.+link/ether\s+(?P<mac>\S+)", output, re.DOTALL)
            if match:
                mac_address = match.group('mac')
                if is_valid_mac(mac_address):
                    return match.group('mac')
                else:
                    logging.error(f"Invalid MAC address received on {rpi}")
                    return False
            else:
                logging.error(f"The subinterface is not configured on the device {ssh.ip}")
                return False
    except socket.timeout as error:
        logging.error(f"An error has occurred on the device - {error}")


def send_script_to_rpi(devices, script_file, rpi):
    try:
        remote_path = "/home/pi/tests/"
        name_of_test: str = "tsins"
        with SFTPParamiko(**devices[rpi]) as sftp:
            # Change directory to /home/pi/tests/
            sftp.change_dir(remote_path)
            # Check tsins directory on rpi
            if name_of_test not in sftp.list_dir():
                sftp.mkdir(name_of_test)
            sftp.change_dir(name_of_test)
            # Send file to /home/pi/tests/tsins/
            sftp.put_file(Path(path_test, script_file), sftp.get_cwd())
            script_path = Path(sftp.get_cwd(), script_file)
        with BaseSSHParamiko(**devices[rpi]) as ssh:
            ssh.send_exec_commands(f"chmod +x {script_path}")
        return script_path
    except (FileNotFoundError, FileExistsError) as error:
        logging.error(f"An error occurred while working with the file '{script_file}' - {error}")
    except OSError as error:
        logging.error(f"An error has occurred on the device {rpi} - {error}")

def is_valid_mac(value):
    allowed = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})$")
    if allowed.match(value) is None:
        return False
    else:
        return True

if __name__ == "__main__":
    tsins_device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi": ["rpi2", "rpi3", "rpi5"],
    }
    # должен передавать ci-cd
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)
    with open(f"{path_connection}/devices.yaml") as file:
        devices = yaml.safe_load(file)

    devices_connection_data_dict = {}
    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values

    timestamp_test(devices_connection_data_dict, tsins_device_dict, network_params)
