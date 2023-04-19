import pytest
import yaml
from pathlib import Path

from ants.auto_tests.timestamp_replacement.tsins import timestamp_test, configure_ssfp, is_valid_mac

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_connection = Path(path_home, 'data', 'connection_data')
path_commands = Path(path_home, 'ants', 'auto_tests', 'timestamp_replacement', 'commands')
path_test_network = Path(path_home, 'data', 'network_test_configs')


@pytest.fixture
def correct_tsins_device_dict():
    tsins_device_dict = {
        "ssfp": ["ssfp4", "ssfp8"],
        "rpi": ["rpi2", "rpi3", "rpi5"],
    }
    return tsins_device_dict


@pytest.fixture
def wrong_tsins_device_dict():
    tsins_device_dict = {
        "ssfp": ["ssfp4"],
        "rpi": ["rpi2"],
    }
    return tsins_device_dict


@pytest.fixture
def device_connection_data_dict():
    with open(f"{path_connection}/devices.yaml") as file:
        devices = yaml.safe_load(file)
    devices_connection_data_dict = {}
    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values
    return devices_connection_data_dict


@pytest.fixture
def network_params():
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)
    return network_params

@pytest.fixture
def wrong_network_params(correct_tsins_device_dict, network_params):
    rpi_src = correct_tsins_device_dict["rpi"][0]
    rpi_dst = correct_tsins_device_dict["rpi"][1]
    rpi_ntp = correct_tsins_device_dict["rpi"][2]

    wrong_network_params = network_params.copy()

    wrong_network_params["rpi"][rpi_src]["vlan"] = 'aaa'
    wrong_network_params["rpi"][rpi_src]["vlan"] = 22222
    wrong_network_params["rpi"][rpi_ntp]["ip"] = 'b'
    wrong_network_params["rpi"][rpi_src]["ip"] = '10.111.1'
    wrong_network_params["rpi"][rpi_dst]["ip"] = 22
    wrong_network_params["rpi"][rpi_src]["interface"] = 1
    return wrong_network_params


def test_wrong_tsins_device_dict(device_connection_data_dict, wrong_tsins_device_dict,
                                  network_params):
    assert timestamp_test(device_connection_data_dict,
                          wrong_tsins_device_dict, network_params) == False

def test_wrong_network_params(device_connection_data_dict, correct_tsins_device_dict,
                                  wrong_network_params):
    assert timestamp_test(device_connection_data_dict,
                          correct_tsins_device_dict, wrong_network_params) == False

def test_configure_ssfp(device_connection_data_dict, correct_tsins_device_dict):
    assert configure_ssfp(device_connection_data_dict, "ssfp_commands.txt",
                        correct_tsins_device_dict["ssfp"][0], "10.10.2.1") == False

@pytest.mark.parametrize(
    ("mac_address", "result"),
    [
        ("dc:cc:22:11:f3:41",  True),
        ("44:22:aa", False),
        ("qq:qq:qq:ww:ww:ww", False),
        ("fa00::aaaa:aaaa:aaa:b3", False),
        ("36:97:91:29:ea:40", True)
    ],
)

def test_is_valid_mac(mac_address, result):
    assert is_valid_mac(mac_address) == result
