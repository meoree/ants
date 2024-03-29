import pytest
import yaml
from pathlib import Path

from ants.auto_tests.timestamp_replacement.tsins import timestamp_test_with_rpi, configure_device, is_valid_mac

path_home = Path(Path.home(), 'python', 'auto_network_test_system')
path_connection = Path(path_home, 'data', 'connection_data')
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
def wrong_rpi_src_vlan(correct_tsins_device_dict, network_params):
    rpi_src = correct_tsins_device_dict["rpi"][0]
    wrong_rpi_src_vlan = network_params.copy()
    wrong_rpi_src_vlan["rpi"][rpi_src]["vlan"] = 'aaa'
    return wrong_rpi_src_vlan
@pytest.fixture
def wrong_rpi_src_ip(correct_tsins_device_dict, network_params):
    rpi_src = correct_tsins_device_dict["rpi"][0]
    wrong_rpi_src_ip = network_params.copy()
    wrong_rpi_src_ip["rpi"][rpi_src]["ip"] = '10.111.1'
    return wrong_rpi_src_ip

@pytest.fixture
def wrong_rpi_dst_vlan(correct_tsins_device_dict, network_params):
    rpi_dst = correct_tsins_device_dict["rpi"][1]
    wrong_rpi_dst_vlan = network_params.copy()
    wrong_rpi_dst_vlan["rpi"][rpi_dst]["vlan"] = 22222
    return wrong_rpi_dst_vlan
@pytest.fixture
def wrong_rpi_dst_ip(correct_tsins_device_dict, network_params):
    rpi_dst = correct_tsins_device_dict["rpi"][1]
    wrong_rpi_dst_ip = network_params.copy()
    wrong_rpi_dst_ip["rpi"][rpi_dst]["ip"] = 22
    return wrong_rpi_dst_ip

@pytest.fixture
def wrong_rpi_ntp_ip(correct_tsins_device_dict, network_params):
    rpi_ntp = correct_tsins_device_dict["rpi"][2]
    wrong_rpi_ntp_ip = network_params.copy()
    wrong_rpi_ntp_ip["rpi"][rpi_ntp]["ip"] = '192.168.256.1'
    return wrong_rpi_ntp_ip

@pytest.fixture
def wrong_rpi_src_intf(correct_tsins_device_dict, network_params):
    rpi_src = correct_tsins_device_dict["rpi"][0]
    wrong_rpi_src_intf = network_params.copy()
    wrong_rpi_src_intf["rpi"][rpi_src]["interface"] = 1
    return wrong_rpi_src_intf

@pytest.fixture
def timestamp_test_params_rpi():
    params = (
        {"pattern1": "AAAAAAAAAAAAAAAA",
         "pattern2": "BBBBBBBBBBBBBBBB",
         "intf1": 1,
         "intf2": 1,
         "direction1": "ingress",
         "direction2": "egress",
         "interval": 0.01,
         "count_of_packets": 2000,
         "packet_size": 1500}
    )
    return params

@pytest.mark.skip(reason="Code test")
def test_wrong_tsins_device_dict(
        device_connection_data_dict, wrong_tsins_device_dict, network_params, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(
        device_connection_data_dict, wrong_tsins_device_dict, network_params, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_wrong_rpi_ntp_ip(device_connection_data_dict, correct_tsins_device_dict,
                                  wrong_rpi_ntp_ip, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(device_connection_data_dict,
                                   correct_tsins_device_dict, wrong_rpi_ntp_ip, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_wrong_rpi_src_ip(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_src_ip, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_src_ip, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_wrong_rpi_dst_ip(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_dst_ip, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_dst_ip, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_wrong_rpi_src_vlan(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_src_vlan, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_src_vlan, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_wrong_rpi_dst_vlan(device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_dst_vlan, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_dst_vlan, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_wrong_rpi_src_intf(
        device_connection_data_dict, correct_tsins_device_dict,wrong_rpi_src_intf, timestamp_test_params_rpi):
    assert timestamp_test_with_rpi(
        device_connection_data_dict, correct_tsins_device_dict, wrong_rpi_src_intf, timestamp_test_params_rpi) == False
@pytest.mark.skip(reason="Code test")
def test_configure_device(device_connection_data_dict, correct_tsins_device_dict, timestamp_test_params_rpi):
    assert configure_device(
        device_connection_data_dict, "ssfp_commands.txt", correct_tsins_device_dict["ssfp"][0],
        timestamp_test_params_rpi) == False

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
@pytest.mark.skip(reason="Code test")
def test_is_valid_mac(mac_address, result):
    assert is_valid_mac(mac_address) == result
