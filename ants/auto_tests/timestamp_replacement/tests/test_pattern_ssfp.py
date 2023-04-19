import pytest

from ants.auto_tests.timestamp_replacement.pattern_ssfp import send_packets


@pytest.mark.parametrize(
    ("mac_dst", "mac_src", "ip_src", "ip_dst", "interface", "vlan", "number_of_test", "result"),
    [
        ("dc:cc:22:11:f3", "dc:cc:22:11:f3:41", "192.168.1.1", "192.168.1.2", "eth", 550, 2, False),
        ("dc:cc:22:11:f3:41", "fa00::aaaa:aaaa:aaa:b3", "192.168.1.1", "192.168.1.2", "eth", 550, 2, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.555.1.1", "192.168.1.2", "eth", 550, 2, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.168.1.1", "aa.aa.aa.aa", "eth", 550, 2, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.168.1.1", "192.168.1.2", 1, 550, 2, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.168.1.1", "192.168.1.2", "eth0", "vlan", 2, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.168.1.1", "192.168.1.2", "eth0", 550, 0, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.168.1.1", "192.168.1.2", "eth0", 550, 6, False),
        ("dc:cc:22:11:f3:41", "dc:cc:22:11:f3:41", "192.168.1.1", "192.168.1.2", "eth0", 550, "number", False),
    ],
)
def test_send_packets(mac_dst, mac_src, ip_src, ip_dst, interface, vlan, number_of_test, result):
    assert send_packets(mac_dst, mac_src, ip_src, ip_dst, interface, vlan, number_of_test) == result
