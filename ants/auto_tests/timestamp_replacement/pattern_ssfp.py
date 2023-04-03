#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from sys import argv
import argparse
import logging

#Remove scapy WARNING message 
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.all import *
from scapy.layers.inet import *
from scapy.layers.l2 import *
from scapy.packet import fuzz


def send_packets(mac_dst, mac_src, ip_src, ip_dst, interface, number_of_test, count_of_packets=1000):
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

    print(mac_dst, mac_src, ip_src, ip_dst, interface)
    try:
        if int(number_of_test) == 1:
            data = pattern1
        elif int(number_of_test) == 2:
            data = pattern1 + pattern2 + fill2
        elif int(number_of_test) == 3:
            data =  pattern1 + fill2 + pattern2 
        elif int(number_of_test) == 4:
            data =  fill2 + pattern1 + pattern2 
        elif int(number_of_test) == 5:
            data =  fill1 + pattern1 + fill1 + pattern2 + fill1 
    except: ValueError

    try:
        vlan = interface.split(".")[1]
    except: IndexError

    packet = (
        fuzz(
        Ether(src=mac_src, dst=mac_dst)
        /Dot1Q(vlan=vlan, id=vlan)
        /IP(src=ip_src, dst=ip_dst, version=4)
        /UDP()
        )
        /data
    )

    try:
        sendp(packet, count=count_of_packets, iface=interface)
    except Scapy_Exception as error:
        print(f"An error occurred while trying to send scapy packets: {error}")
  
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
                        help='The interface from that the packets will be sent in the format "eth0.50"')
    parser.add_argument('number_of_test', type=int, 
                        help='Number of test')
    args = vars(parser.parse_args())
    send_packets(**args)

