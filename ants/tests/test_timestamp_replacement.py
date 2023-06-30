import pytest
import yaml
from pathlib import Path

from ants.auto_tests.timestamp_replacement.tsins import timestamp_test_with_rpi, timestamp_test_with_bercut

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_connection = Path(path_home, 'data', 'connection_data')
path_test_network = Path(path_home, 'data', 'network_test_configs')


@pytest.fixture
def devices_connection_data_dict():
    with open(f"{path_connection}/devices.yaml") as file:
        devices = yaml.safe_load(file)
    devices_connection_data_dict = {}
    for _, device in devices.items():
        for keys, values in device.items():
            devices_connection_data_dict[keys] = values
    return devices_connection_data_dict


@pytest.fixture
def all_devices_for_test():
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)
    all_devices_for_test = {}
    for device_type, device in network_params.items():
        all_devices_for_test[device_type] = list(device.keys())
    return all_devices_for_test


@pytest.fixture
def network_params():
    with open(f"{path_test_network}/network_params_for_test.yaml") as file:
        network_params = yaml.safe_load(file)
    return network_params


@pytest.mark.parametrize(
    ("timestamp_test_params_rpi", "result_rpi"),
    # pattern1, intf1, direction1 for ssfp1
    # pattern2, intf2, direction2 for ssfp2
    [
        ({"pattern1": "AAAAAAAAAAAAAAAA",
          "pattern2": "BBBBBBBBBBBBBBBB",
          "intf1": 1,
          "intf2": 1,
          "direction1": "ingress",
          "direction2": "egress",
          "interval": 0.01,
          "count_of_packets": 2000,
          "packet_size": 1500},
         True),
        ({"pattern1": "DDDDDDDDDDDDDDDD",
          "pattern2": "AAAA1111BBBB2222",
          "intf1": 0,
          "intf2": 0,
          "direction1": "egress",
          "direction2": "ingress",
          "interval": 0.1,
          "count_of_packets": 1000,
          "packet_size": 60},
         True),
        ({"pattern1": "FFFFFFFFFFFFFFFF",
          "pattern2": "0000000000000000",
          "intf1": 0,
          "intf2": 1,
          "direction1": "ingress",
          "direction2": "egress",
          "interval": 0.02,
          "count_of_packets": 1500,
          "packet_size": 300},
         True),
        ({"pattern1": "AAAA4444CCCC5555",
          "pattern2": "2222222222222222",
          "intf1": 1,
          "intf2": 0,
          "direction1": "ingress",
          "direction2": "egress",
          "interval": 0.01,
          "count_of_packets": 6000,
          "packet_size": 1024},
         True),
    ],
)
@pytest.mark.cli
@pytest.mark.short
@pytest.mark.sw_02
def test_timestamp_short(devices_connection_data_dict, all_devices_for_test, network_params,
                         timestamp_test_params_rpi, result_rpi):
    assert timestamp_test_with_rpi(devices_connection_data_dict, all_devices_for_test, network_params,
                                   timestamp_test_params_rpi) == result_rpi

@pytest.mark.parametrize(
    ("timestamp_test_params_bercut", "result_etn"),
    [
        # pattern, intf1, direction1 for ssfp1
        # pattern, intf2, direction2 for ssfp2
        ({"pattern": "ABCD0123",
          "intf1": 1,
          "intf2": 1,
          "direction1": "ingress",
          "direction2": "egress",
          "duration": "00:05:00",  # in format hh:mm:ss
          "rate": 40,  # use a rate value of up to 40%, otherwise erspan will drop the packets and not forward them.
          "packet_size": 1518},
         True),
        # pattern, intf1, direction1 for ssfp1
        # pattern, intf2, direction2 for ssfp2
        ({"pattern": "C3B5D9A8",
          "intf1": 0,
          "intf2": 0,
          "direction1": "ingress",
          "direction2": "ingress",
          "duration": "00:05:00",  # in format hh:mm:ss
          "rate": 40,  # use a rate value of up to 40%, otherwise erspan will drop the packets and not forward them.
          "packet_size": 1256},
         True),
    ],
)

@pytest.mark.cli
@pytest.mark.long
@pytest.mark.sw_02
def test_timestamp_long(devices_connection_data_dict, all_devices_for_test, network_params,
                        timestamp_test_params_bercut, result_etn):
    assert timestamp_test_with_bercut(devices_connection_data_dict, all_devices_for_test, network_params,
                                      timestamp_test_params_bercut) == result_etn
