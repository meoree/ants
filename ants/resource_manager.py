import logging
from pathlib import Path
import yaml

from rich.logging import RichHandler

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_test_network = Path(path_home, 'data', 'network_test_configs')


class ResourceManager:
    def __init__(self):
        with open(f"{path_test_network}/network_params_for_test.yaml") as file:
            self.network_params = yaml.safe_load(file)

        self.all_devices_for_test = {}

        for device_type, device in self.network_params.items():
            self.all_devices_for_test[device_type] = list(device.keys())

    def get_all_devices_for_test(self):
        return self.all_devices_for_test

    def get_network_params_for_test(self):
        return self.network_params
