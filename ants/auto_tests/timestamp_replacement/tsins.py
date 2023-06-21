# -*- coding: utf-8 -*-
"""
TIMESTAMP REPLACEMENT (TSINS) TEST

Testing the tsins function on the M720.
When traffic passes through the M720 in transit, the twins service on two M720 replaces
timestamps instead of patterns in the packet data field.

There are two implementations of the test:

1. timestamp_test_with_rpi - short test
Packets with patterns are generated on RPi using scapy and sent.
Traffic with timestamps comes to another RPi, where dump is captured.

2. timestamp_test_with_bercut - long test
Packets with patterns are generated on BERcut-ET using BERT test.
The BERT test is sent from BERcut port A to port B, where the loopback is configured,
and the packets are forwarded back through the M720 in transit.
On the first M720, which, when traffic passes in the opposite direction,
the last one is configured with erspan, which redirects packets to the ntp server.
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


def timestamp_test_with_rpi(devices_connection_data: dict, tsins_device: dict,
                            tsins_network_params: dict, timestamp_test_params: dict) -> bool:
    """
    Sets up the services needed to run the test with rpi,
    starts the test, stops the services, returns the result.

    :param devices_connection_data: dictionary with data for connecting to devices
    :param tsins_device: dictionary of lists with devices on which the test will run
    :param tsins_network_params: dictionary with IP-addresses and VLANs for devices used in the test
    :param timestamp_test_params: dictionary with parameters for the timestamp test
    :return: True: if the test runs successfully, otherwise False
    """
    logging.info( "-" * 100)
    logging.info("PREPARATION FOR THE TEST - timestamp_test_with_rpi")
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

        count_of_packets = timestamp_test_params['count_of_packets']

        for vlan in [vlan_src, vlan_dst]:
            if int(vlan) > 4000 or int(vlan) < 2:
                logging.error("Invalid vlan in network parameters for test")
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

    if not correct_value or not check_timestamp_test_params_with_rpi(timestamp_test_params):
        logging.error("Invalid timestamp test parameters for rpi test")
        return False

    mac_src = get_rpi_settings_for_script(devices_connection_data, rpi_src, vlan_src)
    mac_dst = get_rpi_settings_for_script(devices_connection_data, rpi_dst, vlan_dst)

    data_for_test = dict(mac_src=mac_src, mac_dst=mac_dst, ip_src=ip_src, ip_dst=ip_dst, intf_src=intf_src,
                             vlan_src=vlan_src, ntp_ip=ntp_ip)
    data_for_test.update(timestamp_test_params)

    with open(Path(path_test, "send_to_rpi_file.yaml"), "w+") as send_to_rpi_file:
        yaml.dump(data_for_test, send_to_rpi_file, default_flow_style=False, sort_keys=False)

    script_path = send_file_to_rpi(devices_connection_data, 'pattern_ssfp.py', rpi_src)
    send_file_to_rpi(devices_connection_data, 'send_to_rpi_file.yaml', rpi_src)

    configure_device(devices_connection_data, "ssfp1_commands.txt", tsins_device["ssfp"][0], data_for_test)
    configure_device(devices_connection_data, "ssfp2_commands.txt", tsins_device["ssfp"][1], data_for_test)

    token = secrets.token_urlsafe(5)
    logging.debug("Token for pcap file: %s", token)

    logging.info("-" * 100)
    logging.info("TEST timestamp_test_with_rpi STARTED")
    with BaseSSHParamiko(**devices_connection_data[rpi_src]) as cl_src:
        with BaseSSHParamiko(**devices_connection_data[rpi_dst]) as cl_dst:
            cl_dst.send_shell_commands(
                ["cd /home/pi/", "mkdir tests", "cd tests", "mkdir tsins", "cd tsins", "mkdir short_tests", "cd short_tests"]
            )
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
            time.sleep(300)

    logging.info("TEST timestamp_test_with_rpi FINISHED")
    logging.info("-" * 100)

    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][0])
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][1])
    logging.info("The services used in the test timestamp_test_with_rpi are stopped")

    logging.info("Check the .pcap file in the test timestamp_test_with_rpi")
    with BaseSSHParamiko(**devices_connection_data[rpi_dst]) as cl:
        cl.send_shell_commands("cd /home/pi/tests/tsins/short_tests/")
        output = cl.send_shell_commands("ls")
        logging.debug(output)
        print(output)
        if token in output:
            logging.info(f"The file stored on the device {ntp_ip} at /home/pi/tests/tsins/short_tests/")
            return True
        logging.error("The .pcap file does not exist")
        return False


def timestamp_test_with_bercut(devices_connection_data: dict, tsins_device: dict,
                               tsins_network_params: dict, timestamp_test_params: dict):
    """
    Sets up the services needed to run the test with BERcut,
    starts the test, stops the services, returns the result.

    :param devices_connection_data: dictionary with data for connecting to devices
    :param tsins_device: dictionary of lists with devices on which the test will run
    :param tsins_network_params: dictionary with IP-addresses and VLANs for devices used in the test
    :param timestamp_test_params: dictionary with parameters for the timestamp test
    :return: True: if the test runs successfully, otherwise False
    """
    logging.info("-" * 100)
    logging.info("PREPARATION FOR THE TEST timestamp_test_with_bercut")
    logging.debug(f"Test parameters for bert test- {timestamp_test_params}")

    try:
        etn = tsins_device["etn"][0]
        rpi_ntp = tsins_device["rpi"][2]
        ntp_ip = tsins_network_params["rpi"][rpi_ntp]["ip"]
        ssfp = tsins_device["ssfp"][0]
        ssfp_ip = tsins_network_params["ssfp"][ssfp]["ip"]

        intf_rpi = tsins_network_params["rpi"][rpi_ntp]["interface"]
        vlan_rpi = tsins_network_params["rpi"][rpi_ntp]["vlan"]

        ip_port_a = tsins_network_params["etn"][etn]["ip_port_a"]
        ip_port_b = tsins_network_params["etn"][etn]["ip_port_b"]

        seconds_for_tcpdump = duration_to_seconds(timestamp_test_params['duration'])

    except (KeyError, IndexError):
        logging.error("3 RPi, 2 SSFP and 1 BERcut-ET should be transmitted")
        return False

    if not check_timestamp_test_params_with_bercut(timestamp_test_params):
        logging.error("Invalid timestamp test params for bercut test")
        return False

    data_for_test = dict(ssfp_ip=ssfp_ip, vlan=vlan_rpi, ip_port_a=ip_port_a, ip_port_b=ip_port_b, ntp_ip=ntp_ip)
    data_for_test.update(timestamp_test_params)

    configure_device(devices_connection_data, "ssfp1_commands.txt", tsins_device["ssfp"][0], data_for_test)
    configure_device(devices_connection_data, "ssfp2_commands.txt", tsins_device["ssfp"][1], data_for_test)
    configure_device(devices_connection_data, "ssfp_erspan.txt", tsins_device["ssfp"][0], data_for_test)
    configure_device(devices_connection_data, "etn_commands.txt", etn, data_for_test)

    token = secrets.token_urlsafe(5)
    logging.debug("Token for pcap file: %s", token)

    logging.info("-" * 100)
    logging.info("TEST timestamp_test_with_bercut STARTED")
    with BaseSSHParamiko(**devices_connection_data[rpi_ntp]) as cl:
        cl.send_shell_commands(
            ["cd /home/pi/", "mkdir tests", "cd tests", "mkdir tsins", "cd tsins", "mkdir long_tests", "cd long_tests"]
        )
        for i in range(1, 4): # [1,2,3]
            output_cl = cl.send_shell_commands(
                f"tcpdump -i {intf_rpi}.{vlan_rpi}  -c 1000 -w "
                f"{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}"
                f"_tsins_{token}.pcap"
            )
            logging.debug(output_cl)
            if seconds_for_tcpdump > 180:
                time.sleep(i * seconds_for_tcpdump//4)
            else:
                break

    logging.info("TEST timestamp_test_with_bercut FINISHED")
    logging.info("-" * 100)
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][0])
    stop_services_ssfp(devices_connection_data, tsins_device["ssfp"][1])
    logging.info("The services used in the test timestamp_test_with_bercut are stopped")

    logging.info("Check pcap file in the test timestamp_test_with_bercut")
    with BaseSSHParamiko(**devices_connection_data[rpi_ntp]) as cl:
        cl.send_shell_commands("cd /home/pi/tests/tsins/long_tests/")
        output = cl.send_shell_commands("ls")
        logging.debug(output)
        if token in output:
            logging.info(f"The file stored on the device {ntp_ip} at /home/pi/tests/tsins/long_tests/")
            return True
        logging.error("The .pcap file does not exist")
        return False




def check_timestamp_test_params_with_rpi(timestamp_test_params: dict) -> bool:
    """
    Checking the correctness of the passed parameters in the dictionary timestamp_test_params

    :param timestamp_test_params: dictionary of timestamp test params for test with rpi
    :return: True if timestamp test params are valid, False otherwise
    """
    logging.debug("Function check_timestamp_test_params_with_rpi started in tsins.py")
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
            logging.debug("Timestamp test parameters for rpi are correct")
            return correct_value
    except (ValueError, KeyError):
        logging.error("Invalid value for timestamp test parameters")
        return False


def check_timestamp_test_params_with_bercut(timestamp_test_params: dict) -> bool:
    """
    Checking the correctness of the passed parameters in the dictionary timestamp_test_params

    :param timestamp_test_params: dictionary of timestamp test params for test with bercut
    :return: True if timestamp test params are valid, False otherwise
    """
    logging.debug("Function check_timestamp_test_params_with_bercut started in tsins.py")
    correct_value = True
    pattern = timestamp_test_params['pattern']
    intf1 = timestamp_test_params["intf1"]
    intf2 = timestamp_test_params["intf2"]
    try:
        int(pattern, 16)
        int(timestamp_test_params["rate"])
        int(timestamp_test_params["packet_size"])
        if len(pattern) != 8:
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
            logging.debug("Timestamp test parameters for bercut are correct")
            return correct_value
    except (ValueError, KeyError):
        logging.error("Invalid value for timestamp test parameters")
        return False


def configure_device(devices_connection_data: dict, file_with_commands: str,
                   device: str,  timestamp_test_params: dict) -> str | bool:
    """Connect to SSFP and configures commands on it from the  file with commands.

    :param devices_connection_data: dictionary with data for connecting to device
    :param file_with_commands: jinja template file which contains commands to be entered on device
    :param device: on which device need to enter commands
    :param timestamp_test_params: parameters for timestamp test
    :return: output: command output from device
             False: if there were any errors while sending commands
    """
    logging.info("Configuring commands on %s", device)
    try:
        if os.stat(Path(path_commands, file_with_commands)).st_size == 0:
            logging.info("File %s is empty", file_with_commands)
            return False
        environment = Environment(loader=FileSystemLoader(path_commands),
                                  trim_blocks=True, lstrip_blocks=True)
        template = environment.get_template(file_with_commands)
        commands = template.render({**timestamp_test_params}).split("\n")
        with BaseSSHParamiko(**devices_connection_data[device]) as ssh:
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
                                              "tsins stop profile0", "erspan stop profile0"])
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


def duration_to_seconds(duration: str) -> int | bool:
    """
    Convert duration to seconds for tcpdump.
    :param duration: duration in format "hh:mm:ss"
    :return: int: seconds
            False: if duration is not valid
    """
    try:
        hours, minutes, seconds = duration.split(":")
        result_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        return result_seconds
    except ValueError:
        logging.error("Invalid duration")
        return False
