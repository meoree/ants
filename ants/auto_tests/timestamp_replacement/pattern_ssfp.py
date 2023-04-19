#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
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


def send_packets(mac_dst, mac_src, ip_src, ip_dst, interface, vlan, number_of_test, count_of_packets=1000):
    """
        Отправляет пакеты с заданными параметрами и вставленными паттернами в поле дата 
        для тестирования функции временных меток на SSFP.
       
        Параметры:
            mac_dst (str): MAC-адрес назначения
            mac_src (str): MAC-адрес источника
            ip_src (str): IP-адрес источника
            ip_dst (str): IP-адрес назначения
            count_of_packets (int): количество пакетов для отправки. По умолчанию 1.

    """
    fill1 = "X" * 484
    pattern1 = "AAAAAAAA"
    fill2 = "X" * 1452
    pattern2 = "BBBBBBBB"

    if not (is_valid_mac(mac_src) and is_valid_mac(mac_dst)):
        logging.error("Invalid MAC address")
        return False
    if type(interface) != str:
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
    except Scapy_Exception as error:
        print(f"An error occurred while trying to send scapy packets: {error}")


def is_valid_mac(value):
    allowed = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})$")
    if allowed.match(value) is None:
        return False
    else:
        return True


def print_timestamp():
    print(f"Timestamp: {time.time()}")


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
    parser.add_argument('interface', type=str,
                        help='The interface from that the packets will be sent in the format "eth0"')
    parser.add_argument('vlan', type=int,
                        help='VLAN')
    parser.add_argument('number_of_test', type=int,
                        help='Number of test (1-5)')
    args = vars(parser.parse_args())
    send_packets(**args)
