# -*- coding: utf-8 -*-
import logging
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from rich.logging import RichHandler

from auto_tests.connection import BaseSSHParamiko, SFTPParamiko, ScanDevices

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


class BaseTest:
    def __init__(self, devices_connection_dict : dict, test_device_list : list, network_params_for_test : dict):
        """
        Docstring for BaseTest.
        """
        self.devices_connection_data_dict = devices_connection_dict
        self.network_params_for_test = network_params_for_test
        self.test_device_list = test_device_list

        self.scan_devices()

        for current_device in self.test_device_list:
            connection_data_dict = self.devices_connection_data_dict[current_device]
            vlan = self.network_params_for_test[current_device]['vlan']
            switch1 = connection_data_dict["switch1"]
            port1 = connection_data_dict["port1"]

            try:
                switch2 = connection_data_dict["switch2"]
                port2 = connection_data_dict["port2"]
                self.configure_switch(switch1, port1, vlan, option='add')
            except KeyError:
                switch2 = None
                port2 = None
            if switch2:
                self.configure_switch(switch2, port2, vlan, option='add')
                pass
            print(current_device)
            self.configure_network_config_file(current_device)

        # self._configure_network()

    def scan_devices(self):
        logging.info("Checking the availability of devices selected for the test")

        scan_test = ScanDevices(self.devices_connection_data_dict, self.test_device_list)
        _, fail = scan_test.scan_devices()
        if fail:
            sys.exit(f"There are devices to which it was not possible to connect - {fail}"
                     f"\nCannot run test.")
        else:
            logging.info("All devices are available")

    def configure_switch(self, switch: str, port: str, vlan: str, option: str) -> str:
        if option == "add" or option == "remove":
            logging.info(f"Configuring port {port} on switch {switch}")
            result = ""
            config_switch_template = ["configure terminal",
                                      f"vlan {vlan}",
                                      f"interface ethernet 1/0/{port}",
                                      f"switchport mode trunk",
                                      f"switchport trunk allowed vlan {option} {vlan}"]

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
                return result
        else:
            logging.error(f"Unknown option {option}, use 'add' or 'remove'")
            return False

    def _template_network_config_file(self, current_params_for_test: dict) -> str:
        env = Environment(loader=FileSystemLoader(path_test_network), trim_blocks=True, lstrip_blocks=True)
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
            logging.error(f"The subinterface: {intf_vlan_network} is already configured on the device")
        else:
            logging.info(f"IP address {ip_network} and subinterface {intf_vlan_network} are free")
            template_network_config = self._template_network_config_file(network_params)
            return template_network_config
        return False

    def configure_network_config_file(self, current_device: str):
        current_params_for_test = self.network_params_for_test[current_device]
        file_path = current_params_for_test["path"]
        with SFTPParamiko(**devices_connection_data_dict[current_device]) as sftp:
            file_content = sftp.read_file(file_path)
            template = self.check_network_config_file(current_params_for_test, file_content)
            if template:
                logging.info("Configuring a subinterface on a device")
                sftp.add_to_file(template, file_path)
                with BaseSSHParamiko(**devices_connection_data_dict[current_device]) as ssh:
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

    devices_connection_data_dict = {}
    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values

    test_device_list = []
    for device, device_params in network_params.items():
            test_device_list.append(device)

    BaseTest(devices_connection_data_dict, test_device_list, network_params)

    # logging.info("TEST TIMESTAMP REPLACE")
    # timestamp_test(devices_connection_data_dict, tsins_device_dict, network_params)
