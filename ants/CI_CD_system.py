import logging
from pathlib import Path

import pytest
import yaml
from rich.logging import RichHandler

from network_manager import ConfigureNetwork, DeconfigureNetwork
from ants.auto_tests.timestamp_replacement.tsins import timestamp_test_with_bercut

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

rpi_config_file_path = "/etc/network/interfaces"
ssfp_config_file_path = "/etc/network/interfaces.d/gbe"


if __name__ == "__main__":
    with open(f"{path_connection}/devices.yaml", encoding="UTF-8") as file:
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

    сonfigure_network = ConfigureNetwork(devices_connection_data_dict, all_devices_for_test, network_params)
    logging.info("TEST TIMESTAMP REPLACE")
    #опция -s включает отображение logging при запуске pytest
    #опция -v включает нормальное отображение тестов в pytest
    retcode = pytest.main(["-c", "tests/test_timestamp_replacement.py", "-m", "stand and short", "-s", "-v"])
    deconfigure_network = DeconfigureNetwork(devices_connection_data_dict, all_devices_for_test, network_params)
