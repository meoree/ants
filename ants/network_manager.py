import logging
import re
import sys
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rich.logging import RichHandler
from connection import BaseSSHParamiko, SFTPParamiko, ScanDevices

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

rpi_config_file_path: str = "/etc/network/interfaces"
ssfp_config_file_path: str = "/etc/network/interfaces.d/gbe"


class ErrorInNetworkManagerException(Exception):
    pass


class BaseNetworkManager:
    def __init__(self, devices_connection_data: dict, all_devices_for_test: dict,
                 network_params_for_test: dict):
        self.devices_connection_data = devices_connection_data
        self.network_params = {}
        self.test_device_list = []

        for _, devices in network_params_for_test.items():
            for dev, dev_values in devices.items():
                self.network_params[dev] = dev_values

        for _, devices in all_devices_for_test.items():
            for element in devices:
                self.test_device_list.append(element)

        self.scan_devices()

    def scan_devices(self):
        logging.info("Checking the availability of devices selected for the test")

        scan_test = ScanDevices(self.devices_connection_data, self.test_device_list)
        _, fail = scan_test.scan_devices()
        if fail:
            sys.exit(f"There are devices to which it was not possible to connect - {fail}"
                     f"\nCannot run test.")
        else:
            logging.info("All devices are available")


class ConfigureNetwork(BaseNetworkManager):
    def __init__(self, devices_connection_data: dict, all_devices_for_test: dict,
                 network_params_for_test: dict):
        super().__init__(devices_connection_data, all_devices_for_test, network_params_for_test)
        self.configure_test()

    def configure_test(self):
        logging.info("Configuring network for test")
        for current_device in self.test_device_list:
            connection_data_dict = self.devices_connection_data[current_device]
            vlan = self.network_params[current_device]['vlan']
            switch1 = connection_data_dict["switch1"]
            port1 = connection_data_dict["port1"]
            self.configure_switch(switch1, port1, vlan)
            try:
                switch2 = connection_data_dict["switch2"]
                port2 = connection_data_dict["port2"]
            except KeyError:
                switch2 = None
                port2 = None
            if switch2:
                self.configure_switch(switch2, port2, vlan)
            if 'ssfp' in current_device:
                file_path = ssfp_config_file_path
                self.configure_network_config_file(current_device, file_path)
            elif 'rpi' in current_device:
                file_path = rpi_config_file_path
                self.configure_network_config_file(current_device, file_path)
            elif 'etn' in current_device:
                self.configure_etn(current_device)
            else:
                raise ErrorInNetworkManagerException(f"Unknown device type: {current_device}")


    def configure_switch(self, switch: str, port: str, vlan: str):
        time.sleep(5)
        if type(vlan) == int:
            pass
        elif type(vlan) == list:
            vlans_str = []
            for vl in vlan:
                vlans_str.append(str(vl))
            vlan = ",".join(vlans_str)
        else:
            logging.error(f"Unknown vlan type {type(vlan)}")
            raise ErrorInNetworkManagerException(f"Error in vlan type {type(vlan)}")

        logging.info(f"Configuring port {port} on switch {switch}")
        config_switch_template = ["configure terminal",
                                  f"vlan {vlan}",
                                  f"interface ethernet 1/0/{port}",
                                  "switchport mode trunk",
                                  f"switchport trunk allowed vlan add {vlan}",
                                  "exit"]

        with BaseSSHParamiko(**self.devices_connection_data[switch]) as ssh:
            output = ssh.send_shell_commands(config_switch_template)
            logging.debug(output)

    def configure_network_config_file(self, current_device: str, file_path: str) -> bool:
        current_params_for_test = self.network_params[current_device]
        output = ""
        with SFTPParamiko(**self.devices_connection_data[current_device]) as sftp:
            file_content = sftp.read_file(file_path)
            template = check_network_config_file(current_params_for_test, file_content)
            if template:
                logging.info(f"Configuring a subinterface on a device {current_device}")
                sftp.add_to_file(template, file_path)
                file_content = sftp.read_file(file_path)
                logging.debug(file_content)
            else:
                return False
        with BaseSSHParamiko(**self.devices_connection_data[current_device]) as ssh:
            ssh.send_shell_commands("reboot")

    def configure_etn(self, current_device: str):
        current_params_for_test = self.network_params[current_device]
        vlan = current_params_for_test['vlan']
        ip_port_a = current_params_for_test['ip_port_a']
        ip_port_b = current_params_for_test['ip_port_b']
        netmask_port_a = current_params_for_test['netmask_port_a']
        netmask_port_b = current_params_for_test['netmask_port_b']
        with BaseSSHParamiko(**self.devices_connection_data[current_device]) as ssh:
            output = ssh.send_shell_commands(
                ["configure", f"network a ip {ip_port_a}", f"network a subnet {netmask_port_a}",
                "gbe a vlan count 1", f"gbe a vlan 1 id {vlan}", f"network b ip {ip_port_b}",
                f"network b subnet {netmask_port_b}", "gbe b vlan count 1",
                f"gbe b vlan 1 id {vlan}", "exit", "show network a", "show network b",
                "show gbe a", "show gbe b"]
            )
        logging.debug(output)


class DeconfigureNetwork(BaseNetworkManager):
    def __init__(self, devices_connection_data: dict, all_devices_for_test: dict,
                 network_params_for_test: dict):
        super().__init__(devices_connection_data, all_devices_for_test, network_params_for_test)
        self.deconfigure_test()

    def deconfigure_test(self):
        logging.info("Deconfiguring network for test")
        for current_device in self.test_device_list:
            connection_data_dict = self.devices_connection_data[current_device]
            vlan = self.network_params[current_device]['vlan']
            switch1 = connection_data_dict["switch1"]
            port1 = connection_data_dict["port1"]
            self.deconfigure_switch(switch1, port1, vlan)
            try:
                switch2 = connection_data_dict["switch2"]
                port2 = connection_data_dict["port2"]
            except KeyError:
                switch2 = None
                port2 = None
            if switch2:
                self.deconfigure_switch(switch2, port2, vlan)
            if 'ssfp' in current_device:
                file_path = ssfp_config_file_path
                self.deconfigure_network_config_file(current_device, file_path)
            elif 'rpi' in current_device:
                file_path = rpi_config_file_path
                self.deconfigure_network_config_file(current_device, file_path)
            elif 'etn' in current_device:
                self.deconfigure_etn(current_device)
            else:
                raise ErrorInNetworkManagerException(f"Unknown device type: {current_device}")


    def deconfigure_network_config_file(self, current_device: str, file_path: str):
        current_default_params = self.devices_connection_data[current_device]
        if 'ssfp' in current_device:
            template = _default_template_network_config_file(current_default_params,
                                                             "ssfp_default_config_template.txt")
        elif 'rpi' in current_device:
            template = _default_template_network_config_file(current_default_params,
                                                             "rpi_default_config_template.txt")
        else:
            raise ErrorInNetworkManagerException(f"Unknown device type: {current_device}")
        if template:
            with SFTPParamiko(**self.devices_connection_data[current_device]) as sftp:
                logging.info("Deconfiguring a subinterface on a device")
                sftp.overwrite_file(template, file_path)
                file_content = sftp.read_file(file_path)
                logging.debug(file_content)
            with BaseSSHParamiko(**self.devices_connection_data[current_device]) as ssh:
                output = ssh.send_exec_commands("reboot")
                logging.debug(output)
                return True
        return False

    def deconfigure_switch(self, switch: str, port: str, vlan: str):
        time.sleep(5)
        if type(vlan) == int:
            pass
        elif type(vlan) == list:
            vlans_str = []
            for vl in vlan:
                vlans_str.append(str(vl))
            vlan = ",".join(vlans_str)
        else:
            logging.error(f"Unknown vlan type {type(vlan)}")
            raise ErrorInNetworkManagerException(f"Unknown vlan type {type(vlan)}")

        logging.info(f"Configuring port {port} on switch {switch}")
        config_switch_template = ["configure terminal",
                                  f"no vlan {vlan}",
                                  f"interface ethernet 1/0/{port}",
                                  "switchport mode trunk",
                                  f"switchport trunk allowed vlan remove {vlan}",
                                  "exit"]

        with BaseSSHParamiko(**self.devices_connection_data[switch]) as ssh:
            output = ssh.send_shell_commands(config_switch_template)
            logging.debug(output)

    def deconfigure_etn(self, current_device: str):
        with BaseSSHParamiko(**self.devices_connection_data[current_device]) as ssh:
            output = ssh.send_shell_commands(
                ["configure", f"network a ip 192.168.1.1", f"network a subnet 255.255.255.0",
                "gbe a vlan count off", f"network b ip 192.168.2.1",
                f"network b subnet 255.255.255.0", "gbe b vlan count off",
                "exit", "show network a", "show network b",
                "show gbe a", "show gbe b"]
            )
        logging.debug(output)


def _default_template_network_config_file(current_default_params: dict,
                                          file_config: str) -> str:
    env = Environment(loader=FileSystemLoader(path_default), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(file_config)
    return template.render(current_default_params)


def _template_network_config_file(current_params_for_test: dict) -> str:
    env = Environment(loader=FileSystemLoader(path_test_network),
                      trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("change_net_config_file.txt")
    return template.render(current_params_for_test)


def check_network_config_file(current_params_for_test: dict, content: str) -> str | bool:
    logging.info("Checking the network interfaces of the device")

    intf_vlan_content = re.findall(r'auto (\S+\d)\.(\d+)', content)
    ip_content = re.findall(r"address (\S+)", content)

    intf_vlan_network = (current_params_for_test["interface"],
                         f"{current_params_for_test['vlan']}")
    ip_network = current_params_for_test["ip"]

    if ip_network in ip_content:
        logging.warning(f"The IP address: {ip_network} is already configured on the device")
    elif intf_vlan_network in intf_vlan_content:
        logging.warning(f"The subinterface: {intf_vlan_network} "
                        f"is already configured on the device")
    else:
        logging.info(f"IP address {ip_network} and subinterface {intf_vlan_network} are free")
        template_network_config = _template_network_config_file(current_params_for_test)
        return template_network_config
    return False
