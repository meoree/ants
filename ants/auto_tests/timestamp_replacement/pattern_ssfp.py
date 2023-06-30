#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script send to rpi and run from rpi.
Script generate packets with pattern using scapy for timestamp replacement test.
"""
import logging
import binascii

import yaml
from scapy.all import Scapy_Exception
from scapy.layers.inet import UDP, IP
from scapy.layers.l2 import Ether, Dot1Q, sendp
from scapy.packet import fuzz

# Remove scapy WARNING message
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)


def send_packets(params: dict) -> bool:
    """Sends packets with the given parameters
       and inserted patterns in the date field to test the timestamp feature on SSFP.

    :param: params: Dictionary with the parameters for scapy
    :return: True if script sent packets
            False: if some error occurred
    """

    pattern1 = params['pattern1']
    pattern2 = params['pattern2']
    packet_size = params['packet_size']
    fill_size_one_pattern = packet_size - 52 - 8
    fill_size_two_patterns = packet_size - 52 - 16

    packet_with_pattern_1 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            /binascii.unhexlify(pattern1)
    )
    packet_with_pattern_2 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            /binascii.unhexlify(pattern2)
    )
    packet_with_pattern_3 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            / binascii.unhexlify(pattern1 + fill_size_one_pattern * "58")
    )
    packet_with_pattern_4 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            / binascii.unhexlify(pattern2 + fill_size_one_pattern * "58")
    )
    packet_with_pattern_5 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            /binascii.unhexlify(pattern1 + pattern2)
    )
    packet_with_pattern_6 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            /binascii.unhexlify(pattern1 + pattern2 + fill_size_two_patterns * "58")
    )
    packet_with_pattern_7 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            /binascii.unhexlify(pattern1 +  fill_size_two_patterns * "58" + pattern2)
    )
    packet_with_pattern_8 = (
            fuzz(
                Ether(src=params['mac_src'], dst=params['mac_dst'])
                / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                / UDP()
            )
            /binascii.unhexlify(fill_size_two_patterns * "58" + pattern1 + pattern2)
    )

    count = params["count_of_packets"]
    iface = params["intf_src"]
    inter = params["interval"]
    try:
        if packet_size == 60:
            count = count // 2
            sendp(packet_with_pattern_1, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_2, count=count, iface=iface, inter=inter)
        elif fill_size_two_patterns < 0:
            count = count // 4
            sendp(packet_with_pattern_1, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_2, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_3, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_4, count=count, iface=iface, inter=inter)
        elif fill_size_two_patterns == 0:
            count = count // 5
            sendp(packet_with_pattern_1, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_2, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_3, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_4, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_5, count=count, iface=iface, inter=inter)
        elif fill_size_two_patterns < 3:
            count = count // 8
            sendp(packet_with_pattern_1, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_2, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_3, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_4, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_5, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_6, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_7, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_8, count=count, iface=iface, inter=inter)
        elif fill_size_two_patterns >= 3:
            count = count // 9
            fill = fill_size_two_patterns // 3
            dop = packet_size - 52 - (fill * 2 + 16)
            packet_with_pattern_9 = (
                    fuzz(
                            Ether(src=params['mac_src'], dst=params['mac_dst'])
                            / Dot1Q(vlan=params['vlan_src'], id=params['vlan_src'])
                            / IP(src=params['ip_src'], dst=params['ip_dst'], version=4, ttl=64)
                            / UDP()
                    )/ binascii.unhexlify(fill * "58" + pattern1 + fill * "58" + pattern2 + dop * "58")
                )

            sendp(packet_with_pattern_1, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_2, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_3, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_4, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_5, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_6, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_7, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_8, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_8, count=count, iface=iface, inter=inter)
            sendp(packet_with_pattern_9, count=count, iface=iface, inter=inter)
        else:
            print("Strange error")
        return False
    except Scapy_Exception:
        return False


if __name__ == "__main__":
    with open("send_to_rpi_file.yaml") as file:
        test_params = yaml.safe_load(file)
    send_packets(test_params)