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
import sys
import secrets

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
                   tsins_network_params: dict, timestamp_test_params: dict) -> bool:
    """Sets up the services needed to run the test,
    starts the test, stops the services, returns the result.

    :param devices_connection_data: dictionary with data for connecting to devices
    :param tsins_device: dictionary of lists with devices on which the test will run
    :param tsins_network_params: dictionary with IP-addresses and VLANs for devices used in the test
     :param timestamp_test_params: dictionary with parameters for the timestamp test
    :return: True: if the test runs successfully
             False: if the test fails
    """
    logging.info("PREPARATION FOR THE TEST")
    logging.debug(f"Test parameters - {timestamp_test_params}")
    correct_value = True

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

        for vlan in [vlan_src, vlan_dst]:
            if int(vlan) > 4000 or int(vlan) < 2:
                correct_value = False

        for ip_address in [ip_dst, ip_src, ntp_ip]:
            if not isinstance(ip_address, str):
                logging.error("Wrong interface in network parameters for test")
                correct_value = False
            else:
                IPv4Address(ip_address)

        if not isinstance(intf_src, str):
            logging.error("Wrong interface in network parameters for test")
            correct_value = False

    except (KeyError, IndexError):
        logging.error("3 RPi and 2 SSFP should be transmitted")
        correct_value = False
    except AddressValueError:
        logging.error("Wrong IP address in network parameters for test")
        correct_value = False
    except ValueError:
        logging.error("VLAN must be a number in network parameters for test")
        correct_value = False

    if not correct_value or not check_timestamp_test_params(timestamp_test_params):
        return False
    mac_src = get_rpi_settings_for_script(devices_connection_data, rpi_src, vlan_src)
    mac_dst = get_rpi_settings_for_script(devices_connection_data, rpi_dst, vlan_dst)

    data_for_rpi_file = dict(mac_src=mac_src, mac_dst=mac_dst, ip_src=ip_src, ip_dst=ip_dst, intf_src=intf_src,
                              vlan_src=vlan_src)
    data_for_rpi_file.update(timestamp_test_params)

    count_of_packets = timestamp_test_params['count_of_packets']

    with open(Path(path_test, "send_to_rpi_file.yaml"), "w+") as send_to_rpi_file:
         yaml.dump(data_for_rpi_file, send_to_rpi_file, default_flow_style=False, sort_keys=False)

    script_path = send_file_to_rpi(devices_connection_data, 'pattern_ssfp.py', rpi_src)
    file_with_parameters = send_file_to_rpi(devices_connection_data, 'send_to_rpi_file.yaml', rpi_src)

    configure_ssfp(devices_connection_data, "ssfp1_commands.txt", tsins_device["ssfp"][0], ntp_ip, timestamp_test_params)
    configure_ssfp(devices_connection_data, "ssfp2_commands.txt", tsins_device["ssfp"][1], ntp_ip, timestamp_test_params)

    token = secrets.token_urlsafe(5)
    logging.debug("Token for pcap file: %s", token)
    with BaseSSHParamiko(**devices_connection_data[rpi_src]) as cl_src:
        with BaseSSHParamiko(**devices_connection_data[rpi_dst]) as cl_dst:
            logging.info("TEST STARTED")
            # tcpdump results stored tests/tsins/
            cl_dst.send_shell_commands(["mkdir tests", "cd tests", "mkdir tsins", "cd tsins"])
            output_dst = cl_dst.send_shell_commands(
                    f"tcpdump -i {intf_src}.{vlan_src} -c {count_of_packets} udp  -w "
                    f"{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}"
                    f"_tsins_{token}.pcap"
            )
            logging.debug(output_dst)
            time.sleep(3)
            cl_src.send_shell_commands("cd /home/pi/tests/tsins/")
            output_src = cl_src.send_shell_commands(f"python3 {script_path}")
            logging.debug(output_src)
            time.sleep(60)
    # Need to send dumps to the server
    logging.info("TEST FINISHED")
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][0])
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][1])
    logging.info("The services used in the test are stopped")

    logging.info("Check pcap file")
    with BaseSSHParamiko(**devices_connection_data[rpi_dst]) as cl:
        cl.send_shell_commands("cd tests/tsins/")
        output = cl.send_shell_commands("ls")
        logging.debug(output)
        print(output)
        if token in output:
            return True
        return False

def check_timestamp_test_params(timestamp_test_params : dict) -> bool:
    """
    :param timestamp_test_params:
    :return:
    """
    logging.debug("Function check_timestamp_test_params started in tsins.py")
    correct_value = True
    pattern1 = timestamp_test_params['pattern1']
    pattern2 = timestamp_test_params['pattern2']
    intf1 = timestamp_test_params["intf1"]
    intf2 = timestamp_test_params["intf2"]
    try:
        int(pattern1, 16)
        int(pattern2, 16)
        int(timestamp_test_params["interval"])
        int(timestamp_test_params["count_of_packets"])
        if len(pattern1) + len(pattern2) != 32:
            correct_value = False
            logging.error("Invalid pattern value in timestamp test parameters")
        elif int(intf1) not in [0, 1] or int(intf2) not in [0, 1]:
            correct_value = False
            logging.error("Invalid interface value in timestamp test parameters")
        elif (timestamp_test_params["direction1"] not in ["egress", "ingress"] or
            timestamp_test_params["direction2"] not in ["egress", "ingress"]):
            correct_value = False
            logging.error("Invalid direction in timestamp test parameters")
        elif int(timestamp_test_params["packet_size"]) < 60 or \
                int(timestamp_test_params["packet_size"]) > 1518:
            correct_value = False
            logging.error("Invalid packet size in timestamp test parameters")
        else:
            return correct_value
    except (ValueError, KeyError):
        logging.error("Invalid value for timestamp test parameters")
        return False


def configure_ssfp(devices_connection_data: dict, file_with_commands: str,
                   ssfp: str, ntp_ip: str, timestamp_test_params : dict) -> str | bool:
    """Connects to SSFP and configures commands on it from the  file with commands.

    :param devices_connection_data: dictionary with data for connecting to ssfp
    :param file_with_commands: jinja template file which contains commands to be entered on SSFP
    :param ssfp: on which ssfp need to enter commands
    :param ntp_ip: ip-address of the ntp server
    :return: output: command output from ssfp
             False: if there were any errors while sending commands
    """
    logging.info("Configuring commands on %s", ssfp)
    try:
        if os.stat(Path(path_commands, file_with_commands)).st_size == 0:
            logging.info("File %s is empty", file_with_commands)
            return False
        environment = Environment(loader=FileSystemLoader(path_commands),
                                  trim_blocks=True, lstrip_blocks=True)
        template = environment.get_template(file_with_commands)
        commands = template.render({'ntp_ip': ntp_ip, **timestamp_test_params}).split("\n")
        with BaseSSHParamiko(**devices_connection_data[ssfp]) as ssh:
            output = ssh.send_shell_commands(commands)
            logging.debug(output)
            return output
    except (FileNotFoundError, FileExistsError) as error:
        logging.error(
            "An error occurred while working with the file '%s' - %s", file_with_commands, error
        )
        return False
    except OSError as error:
        logging.error("An error has occurred on the device - %s", error)
        return False


def stop_services_ssfp(devices_connection_data: dict, ssfp: str) -> bool:
    """Stops all services that were running on ssfp

    :param devices_connection_data: dictionary with data for connecting to ssfp
    :param ssfp: on which ssfp need to stop services
    :return: True: services stopped
             False: if there were any errors while sending commands
    """
    logging.info("Stopping services on device %s", ssfp)
    try:
        with BaseSSHParamiko(**devices_connection_data[ssfp]) as ssh:
            output = ssh.send_shell_commands(["run-klish", "configure terminal",
                                              "timesync stop profile0",
                                              "tsins stop profile0"])
            logging.debug(output)
            return True
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
    logging.info("Getting MAC address from %s", rpi)
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


def send_file_to_rpi(devices_connection_data: dict, file_path: str, rpi: str) -> Path | bool:
    """Sends script with pattern to rpi

    :param devices_connection_data: dictionary with data for connecting to rpi
    :param file_path: file local path to script that send to rpi
    :param rpi: on which rpi send the command
    :return: Path: script path
            False: if some error occurred
    """
    logging.info("Sending script '%s' to device %s", file_path, rpi)
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
            sftp.put_file(Path(path_test, file_path), sftp.get_cwd())
            file_path = Path(sftp.get_cwd(), file_path)
        with BaseSSHParamiko(**devices_connection_data[rpi]) as ssh:
            ssh.send_exec_commands(f"chmod +x {file_path}")
        return file_path
    except (FileNotFoundError, FileExistsError) as error:
        logging.error("An error occurred while working with the file '%s' - %s", file_path, error)
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



