#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import pexpect
import paramiko
import re
import yaml
import logging
import time
import logging
from pathlib import Path
from sys import argv
from rich.logging import RichHandler
from jinja2 import Environment, FileSystemLoader
from pprint import pprint

from ants.auto_tests.connection import BaseSSHParamiko

#Remove scapy WARNING message 
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.all import *
from scapy.layers.inet import *
from scapy.layers.l2 import *
from scapy.packet import fuzz


logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_test = Path(Path.cwd(), 'ants', 'tests', 'timestamp_replacement')
path_connection = Path(Path.cwd(), 'data', 'connection_data')
path_commands = Path(Path.cwd(), 'ants', 'auto_tests', 'timestamp_replacement', 'commands')
        
def send_packets(mac_dst, mac_src, ip_src, ip_dst, number_of_test, count_of_packets=1):
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

        packet = (
            fuzz(
            Ether(src=mac_src, dst=mac_dst)
            /Dot1Q(vlan=550, id=550)
            /IP(src=ip_src, dst=ip_dst, version=4)
            /UDP()
            )
            /data
        )
        sendp(packet, count=count_of_packets, iface="eth0.550")
    
def print_timestamp(): 
            print(f"Timestamp: {time.time()}")

def timestamp_test_start(device_dict):
    with open(f"{path_connection}/devices.yaml") as file:
        devices  = yaml.safe_load(file)
    with open(f"{path_commands}/ssfp1_commands.txt") as file:
        ssfp1_commands = file.read().split('\n')
    ssfp1, ssfp2 = device_dict["ssfp"]
    try:
        connection1 = BaseSSHParamiko(**devices[ssfp1])
        output = connection1.send_shell_commands(["run-klish", "conf t", "show version", "show timesync results profile0"])
        connection1.close()
    except OSError as error:
         logging.error(f"На устройстве {ssfp1} возникла ошибка - {error}")
    return output

   

if __name__ == "__main__":
    timestamp_test_start()




        
