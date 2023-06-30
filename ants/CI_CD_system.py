import logging
from pathlib import Path

import pytest
import yaml
from rich.logging import RichHandler

from network_manager import ConfigureNetwork, DeconfigureNetwork
from resource_manager import ResourceManager

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_connection = Path(path_home, 'data', 'connection_data')


if __name__ == "__main__":
    with open(f"{path_connection}/devices.yaml", encoding="UTF-8") as file:
        devices = yaml.safe_load(file)

    devices_connection_data_dict = {}

    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values

    resource_manager = ResourceManager()
    all_devices_for_test = resource_manager.get_all_devices_for_test()
    network_params = resource_manager.get_network_params_for_test()

    сonfigure_network = ConfigureNetwork(devices_connection_data_dict, all_devices_for_test, network_params)

    options_for_test: str = "short and sw_02"

    logging.info(">>>>> Tests with options %s start <<<<<", options_for_test)
    # опция -s включает отображение logging при запуске pytest
    # опция -v включает нормальное отображение тестов в pytest
    retcode = pytest.main(["-s", "-v", "-m", options_for_test])
    deconfigure_network = DeconfigureNetwork(devices_connection_data_dict, all_devices_for_test, network_params)

