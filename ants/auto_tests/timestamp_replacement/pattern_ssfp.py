#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script send to rpi and run from rpi.
Script generate packets with pattern using scapy for timestamp replacement test.
"""
import argparse
import logging
import re
from ipaddress import IPv4Address, AddressValueError

from scapy.all import Scapy_Exception
from scapy.layers.inet import UDP, IP
from scapy.layers.l2 import Ether, Dot1Q, sendp
from scapy.packet import fuzz

# Remove scapy WARNING message
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)


def send_packets(mac_dst: str, mac_src: str, ip_src: str, ip_dst: str,
                 interface: str, vlan: int, number_of_test: int, count_of_packets=1000) -> bool:
    """Sends packets with the given parameters
       and inserted patterns in the date field to test the timestamp feature on SSFP.

    :param mac_dst: destination MAC address
    :param mac_src: source MAC address
    :param ip_src: destination IP address
    :param ip_dst: source IP address
    :param interface: interface name
    :param vlan: VLAN ID
    :param number_of_test: number of test (1-5)
    :param count_of_packets: default count of packets = 1000
    :return: True if script sent packets
            False: if some error occurred
    """

    fill1 = "X" * 484
    pattern1 = "AAAAAAAA"
    fill2 = "X" * 1452
    pattern2 = "BBBBBBBB"

    if not (is_valid_mac(mac_src) and is_valid_mac(mac_dst)):
        logging.error("Invalid MAC address")
        return False
    if not isinstance(interface, str):
        logging.error("Invalid interface")
        return False
    try:
        IPv4Address(ip_src)
        IPv4Address(ip_dst)
        vlan = int(vlan)
        if int(number_of_test) == 1:
            data = pattern1
        elif int(number_of_test) == 2:
            data = pattern1 + pattern2 + fill2
        elif int(number_of_test) == 3:
            data = pattern1 + fill2 + pattern2
        elif int(number_of_test) == 4:
            data = fill2 + pattern1 + pattern2
        elif int(number_of_test) == 5:
            data = fill1 + pattern1 + fill1 + pattern2 + fill1
        else:
            logging.error("Invalid number of tests")
            return False
    except AddressValueError:
        logging.error("Invalid IP-address")
        return False
    except ValueError:
        logging.error("Invalid number of tests")
        return False


    packet_with_pattern = (
            fuzz(
                Ether(src=mac_src, dst=mac_dst)
                / Dot1Q(vlan=vlan, id=vlan)
                / IP(src=ip_src, dst=ip_dst, version=4)
                / UDP()
            )
            / data
    )

    try:
        sendp(packet_with_pattern, count=count_of_packets, iface=interface)
        return True
    except Scapy_Exception:
        return False


def is_valid_mac(value : str) -> bool:
    """Check if the MAC address is valid

        :param value: MAC address
        :return: True: if the MAC address is valid
                False: otherwise
        """
    template = r"(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})$"
    allowed = re.compile(template)
    if allowed.match(value):
        return True
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send scapy packets with pattern')
    parser.add_argument('mac_src', type=str,
                        help='Source MAC-address in the format "aa:bb:cc:dd:ee:ff"')
    parser.add_argument('mac_dst', type=str,
                        help='Destination MAC-address in the format "aa:bb:cc:dd:ee:ff"')
    parser.add_argument('ip_src', type=str,
                        help='Source IPv4-address')
    parser.add_argument('ip_dst', type=str,
                        help='Destination IPv4-address')
    parser.add_argument(
        'interface', type=str,
        help='The interface from that the packets will be sent in the format "eth0"'
    )
    parser.add_argument('vlan', type=int,
                        help='VLAN')
    parser.add_argument('number_of_test', type=int,
                        help='Number of test (1-5)')
    args = vars(parser.parse_args())
    send_packets(**args)
