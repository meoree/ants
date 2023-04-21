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

from ipaddress import IPv4Address, AddressValueError
import yaml
from rich.logging import RichHandler
from jinja2 import Environment, FileSystemLoader

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


def timestamp_test(devices_connection_data: dict, tsins_device: dict,
                   tsins_network_params: dict) -> bool:
    """Sets up the services needed to run the test,
    starts the test, stops the services, returns the result.

    :param devices_connection_data: dictionary with data for connecting to devices
    :param tsins_device: dictionary of lists with devices on which the test will run
    :param tsins_network_params: dictionary with IP-addresses and VLANs for devices used in the test
    :return: True: if the test runs successfully
             False: if the test fails
    """
    logging.info("PREPARATION FOR THE TEST")

    try:
        rpi_src = tsins_device["rpi"][0]
        rpi_dst = tsins_device["rpi"][1]
        rpi_ntp = tsins_device["rpi"][2]

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

    if not isinstance(intf_src, str):
        logging.error("Wrong interface in network parameters for test")
        return False

    configure_ssfp(devices_connection_data, "ssfp1_commands.txt", tsins_device["ssfp"][0], ntp_ip)
    configure_ssfp(devices_connection_data, "ssfp2_commands.txt", tsins_device["ssfp"][1], ntp_ip)

    mac_src = get_rpi_settings_for_script(devices_connection_data, rpi_src, vlan_src)
    mac_dst = get_rpi_settings_for_script(devices_connection_data, rpi_dst, vlan_dst)

    script_path = send_script_to_rpi(devices_connection_data, 'pattern_ssfp.py', rpi_src)

    with BaseSSHParamiko(**devices_connection_data[rpi_src]) as cl_src:
        with BaseSSHParamiko(**devices_connection_data[rpi_dst]) as cl_dst:
            logging.info("TEST STARTED")
            # tcpdump results stored /tests/tsins/
            cl_dst.send_shell_commands(["mkdir tests", "cd tests", "mkdir tsins", "cd tsins"])
            for number_of_test in range(1, 6):
                logging.info("Number of test: %s", number_of_test)
                output_dst = cl_dst.send_shell_commands(
                    f"tcpdump -i {intf_src}.{vlan_src} -c 1000 -w "
                    f"{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}"
                    f"_tsins_{number_of_test}.pcap"
                )
                logging.debug(output_dst)
                time.sleep(3)
                output_src = cl_src.send_shell_commands(
                    f"python3 {script_path} {mac_src} {mac_dst} {ip_src} "
                    f"{ip_dst} {intf_src} {vlan_src} {number_of_test}"
                )
                logging.debug(output_src)
                time.sleep(5)
    # Need to send dumps to the server
    logging.info("TEST FINISHED")
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][0])
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][1])
    logging.info("The services used in the test are stopped")
    return True


def configure_ssfp(devices_connection_data: dict, file_with_commands: str,
                   ssfp: str, ntp_ip: str) -> str | bool:
    """Connects to SSFP and configures commands on it from the  file with commands.

    :param devices_connection_data: dictionary with data for connecting to ssfp
    :param file_with_commands: jinja template file which contains commands to be entered on SSFP
    :param ssfp: on which ssfp need to enter commands
    :param ntp_ip: ip-address of the ntp server
    :return: output: command output from ssfp
             False: if there were any errors while sending commands
    """
    try:
        if os.stat(Path(path_commands, file_with_commands)).st_size == 0:
            logging.info("File %s is empty", file_with_commands)
            return False
        environment = Environment(loader=FileSystemLoader(path_commands),
                                  trim_blocks=True, lstrip_blocks=True)
        template = environment.get_template(file_with_commands)
        commands = template.render({'ntp_ip': ntp_ip}).split("\n")
        with BaseSSHParamiko(**devices_connection_data[ssfp]) as ssh:
            output = ssh.send_shell_commands(commands)
            logging.debug(output)
            return output
    except (FileNotFoundError, FileExistsError) as error:
        logging.error(
            "An error occurred while working with the file '%s' - %s", file_with_commands, error
        )
    except OSError as error:
        logging.error("An error has occurred on the device - %s", error)
    return False


def stop_services_ssfp(devices_connection_data: dict, ssfp: str) -> str | bool:
    """Stops all services that were running on ssfp

    :param devices_connection_data: dictionary with data for connecting to ssfp
    :param ssfp: on which ssfp need to stop services
    :return: output: command output from ssfp
             False: if there were any errors while sending commands
    """
    try:
        with BaseSSHParamiko(**devices_connection_data[ssfp]) as ssh:
            output = ssh.send_shell_commands(["run-klish", "configure terminal",
                                              "timesync stop profile0",
                                              "tsins stop profile0"])
            logging.debug(output)
            return output
    except OSError as error:
        logging.error("An error has occurred on the device %s - %s", ssh.ip, error)
        return False


def get_rpi_settings_for_script(devices_connection_data: dict, rpi: str, vlan: int) -> str | bool:
    """Sends the "ip a" command to the device and,
    based on the output of this command, looks for the MAC address of the interface

    :param devices_connection_data: dictionary with data for connecting to rpi
    :param rpi: on which rpi send the command
    :param vlan: vlan ID of the interface
    :return: str: MAC address of the interface
            False: if the interface is not configured on the device or invalid mac address received
    """
    try:
        with BaseSSHParamiko(**devices_connection_data[rpi]) as ssh:
            output = ssh.send_exec_commands("ip a")
            match = re.search(rf"\w+.{vlan}.+link/ether\s+(?P<mac>\S+)", output, re.DOTALL)
            if match:
                mac_address = match.group('mac')
                if is_valid_mac(mac_address):
                    return match.group('mac')
                logging.error("Invalid MAC address received on %s", rpi)
                return False
            logging.error("The subinterface is not configured on the device %s", ssh.ip)
            return False
    except socket.timeout as error:
        logging.error("An error has occurred on the device - %s", error)
        return False


def send_script_to_rpi(devices_connection_data: dict, script_file: str, rpi: str) -> Path | bool:
    """Sends script with pattern to rpi

    :param devices_connection_data: dictionary with data for connecting to rpi
    :param script_file: file local path to script that send to rpi
    :param rpi: on which rpi send the command
    :return: Path: script path
            False: if some error occurred
    """
    try:
        remote_path = "/home/pi/tests/"
        name_of_test: str = "tsins"
        with SFTPParamiko(**devices_connection_data[rpi]) as sftp:
            # Change directory to /home/pi/tests/
            sftp.change_dir(remote_path)
            # Check tsins directory on rpi
            if name_of_test not in sftp.list_dir():
                sftp.mkdir(name_of_test)
            sftp.change_dir(name_of_test)
            # Send file to /home/pi/tests/tsins/
            sftp.put_file(Path(path_test, script_file), sftp.get_cwd())
            script_path = Path(sftp.get_cwd(), script_file)
        with BaseSSHParamiko(**devices_connection_data[rpi]) as ssh:
            ssh.send_exec_commands(f"chmod +x {script_path}")
        return script_path
    except (FileNotFoundError, FileExistsError) as error:
        logging.error("An error occurred while working with the file '%s' - %s", script_file, error)
        return False
    except OSError as error:
        logging.error("An error has occurred on the device %s - %s", rpi, error)
        return False


def is_valid_mac(value: str) -> bool:
    """Check if the MAC address is valid

    :param value: MAC address
    :return: True: if the MAC address is valid
            False: otherwise
    """
    template = r"(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})$"
    allowed = re.compile(template)
    if allowed.match(value):
        return True
    return False


if __name__ == "__main__":
    tsins_device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi": ["rpi2", "rpi3", "rpi5"],
    }
    with open(f"{path_test_network}/network_params_for_test.yaml", encoding='UTF-8') as file:
        network_params = yaml.safe_load(file)
    with open(f"{path_connection}/devices.yaml", encoding='UTF-8') as file:
        devices = yaml.safe_load(file)

    devices_connection_data_dict = {}
    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values

    timestamp_test(devices_connection_data_dict, tsins_device_dict, network_params)
