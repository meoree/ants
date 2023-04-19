# -*- coding: utf-8 -*-
"""
Docstring
"""
import logging
import re
import sys
import time
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from rich.logging import RichHandler

from auto_tests.timestamp_replacement.tsins import timestamp_test
from auto_tests.connection import BaseSSHParamiko, SFTPParamiko, ScanDevices

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.DEBUG,
    handlers=[RichHandler()]
)

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_default = Path(path_home, 'data', 'default_configs')
path_test = Path(path_home, 'ants', 'tests', 'timestamp_replacement')
path_connection = Path(path_home, 'data', 'connection_data')
path_commands = Path(path_home, 'ants', 'auto_tests', 'timestamp_replacement', 'commands')
path_test_network = Path(path_home, 'data', 'network_test_configs')

rpi_config_file_path = "/etc/network/interfaces"
ssfp_config_file_path = "/etc/network/interfaces.d/gbe"


class BaseTest:
    def __init__(self, devices_connection_dict: dict, all_devices_for_test: dict,
                 network_params_for_test: dict):
        """
        Docstring for BaseTest.
        """
        self.devices_connection_data_dict = devices_connection_dict
        self.network_params = {}
        self.test_device_list = []

        for device_type, devices in network_params_for_test.items():
            for dev, dev_values in devices.items():
                self.network_params[dev] = dev_values

        for device_type, devices in all_devices_for_test.items():
            for element in devices:
                self.test_device_list.append(element)

        self.scan_devices()

    def configure_test(self):
        for current_device in self.test_device_list:
            connection_data_dict = self.devices_connection_data_dict[current_device]
            vlan = self.network_params[current_device]['vlan']
            switch1 = connection_data_dict["switch1"]
            port1 = connection_data_dict["port1"]
            self.configure_switch(switch1, port1, vlan, option='add')
            try:
                switch2 = connection_data_dict["switch2"]
                port2 = connection_data_dict["port2"]
            except KeyError:
                switch2 = None
                port2 = None
            if switch2:
                self.configure_switch(switch2, port2, vlan, option='add')
            if 'ssfp' in current_device:
                file_path = ssfp_config_file_path
            elif 'rpi' in current_device:
                file_path = rpi_config_file_path
            else:
                raise ValueError("Error")
            self.configure_network_config_file(current_device, file_path)

    def deconfidure_test(self):
        for current_device in self.test_device_list:
            connection_data_dict = self.devices_connection_data_dict[current_device]
            vlan = self.network_params[current_device]['vlan']
            switch1 = connection_data_dict["switch1"]
            port1 = connection_data_dict["port1"]
            self.configure_switch(switch1, port1, vlan, option='remove')
            try:
                switch2 = connection_data_dict["switch2"]
                port2 = connection_data_dict["port2"]
            except KeyError:
                switch2 = None
                port2 = None
            if switch2:
                self.configure_switch(switch2, port2, vlan, option='remove')
            if 'ssfp' in current_device:
                file_path = ssfp_config_file_path
            elif 'rpi' in current_device:
                file_path = rpi_config_file_path
            else:
                raise ValueError("Error")
            self.deconfigure_network_config_file(current_device, file_path)

    def scan_devices(self):
        logging.info("Checking the availability of devices selected for the test")

        scan_test = ScanDevices(self.devices_connection_data_dict, self.test_device_list)
        _, fail = scan_test.scan_devices()
        if fail:
            sys.exit(f"There are devices to which it was not possible to connect - {fail}"
                     f"\nCannot run test.")
        else:
            logging.info("All devices are available")

    def configure_switch(self, switch: str, port: str, vlan: str, option: str):
        time.sleep(5)
        if option == "add" or option == "remove":
            logging.info(f"Configuring port {port} on switch {switch}")
            result = ""
            config_switch_template = ["configure terminal",
                                      f"vlan {vlan}",
                                      f"interface ethernet 1/0/{port}",
                                      "switchport mode trunk",
                                      f"switchport trunk allowed vlan {option} {vlan}",
                                      "exit"]

            with BaseSSHParamiko(**devices_connection_data_dict[switch]) as ssh:
                if type(vlan) == int:
                    result = ssh.send_shell_commands(config_switch_template)
                elif type(vlan) == list:
                    vlans_str = []
                    for vl in vlan:
                        vlans_str.append(str(vl))
                    vlan = ",".join(vlans_str)
                    result = ssh.send_shell_commands(config_switch_template)
                else:
                    logging.error(f"Unknown vlan type {type(vlan)}")
                logging.debug(result)
        else:
            logging.error(f"Unknown option {option}, use 'add' or 'remove'")

    def _template_network_config_file(self, current_params_for_test: dict) -> str:
        env = Environment(loader=FileSystemLoader(path_test_network),
                          trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("change_net_config_file.txt")
        return template.render(current_params_for_test)

    def check_network_config_file(self, current_params_for_test: dict, content: str) -> str | bool:
        logging.info("Checking the network interfaces of the device")

        intf_vlan_content = re.findall(r'auto (\S+\d)\.(\d+)', content)
        ip_content = re.findall(r"address (\S+)", content)

        intf_vlan_network = (current_params_for_test["interface"],
                             f"{current_params_for_test['vlan']}")
        ip_network = current_params_for_test["ip"]

        if ip_network in ip_content:
            logging.error(f"The IP address: {ip_network} is already configured on the device")
        elif intf_vlan_network in intf_vlan_content:
            logging.error(f"The subinterface: {intf_vlan_network} "
                          f"is already configured on the device")
        else:
            logging.info(f"IP address {ip_network} and subinterface {intf_vlan_network} are free")
            template_network_config = self._template_network_config_file(current_params_for_test)
            return template_network_config
        return False

    def configure_network_config_file(self, current_device: str, file_path: str):
        current_params_for_test = self.network_params[current_device]
        with SFTPParamiko(**devices_connection_data_dict[current_device]) as sftp:
            file_content = sftp.read_file(file_path)
            template = self.check_network_config_file(current_params_for_test, file_content)
            if template:
                logging.info("Configuring a subinterface on a device")
                sftp.add_to_file(template, file_path)
                file_content = sftp.read_file(file_path)
                logging.debug(file_content)
            with BaseSSHParamiko(**devices_connection_data_dict[current_device]) as ssh:
                ssh.send_exec_commands("sudo systemctl restart networking.service")

    def _default_template_network_config_file(self, current_default_params: dict,
                                              file_config: str) -> str:
        env = Environment(loader=FileSystemLoader(path_default), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template(file_config)
        return template.render(current_default_params)

    def deconfigure_network_config_file(self, current_device: str, file_path: str):
        current_default_params = self.devices_connection_data_dict[current_device]
        if 'ssfp' in current_device:
            template = self._default_template_network_config_file(current_default_params,
                                                                  "ssfp_default_config_template.txt")
        elif 'rpi' in current_device:
            template = self._default_template_network_config_file(current_default_params,
                                                                  "rpi_default_config_template.txt")
        else:
            raise ValueError("Error")
        if template:
            with SFTPParamiko(**devices_connection_data_dict[current_device]) as sftp:
                logging.info("Deconfiguring a subinterface on a device")
                sftp.overwrite_file(template, file_path)
                file_content = sftp.read_file(file_path)
                logging.debug(file_content)
            with BaseSSHParamiko(**devices_connection_data_dict[current_device]) as ssh:
                ssh.send_exec_commands("sudo systemctl restart networking.service")


if __name__ == "__main__":
    with open(f"{path_connection}/devices.yaml") as file:
        devices = yaml.safe_load(file)
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)

    devices_connection_data_dict = {}
    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values

    all_devices_for_test = {}
    for device_type, device in network_params.items():
        all_devices_for_test[device_type] = list(device.keys())

    test1 = BaseTest(devices_connection_data_dict, all_devices_for_test, network_params)
    test1.configure_test()
    logging.info("TEST TIMESTAMP REPLACE")
    timestamp_test(devices_connection_data_dict, all_devices_for_test, network_params)
    test1.deconfidure_test()
