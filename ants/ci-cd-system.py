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
import socket
from pathlib import Path
from sys import argv
from rich.logging import RichHandler
from jinja2 import Environment, FileSystemLoader
from pprint import pprint


from tests.timestamp_replacement import pattern_ssfp


logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.INFO,
    handlers=[RichHandler()]
)

path_test = Path(Path.cwd(), 'ants', 'tests', 'timestamp_replacement')
path_config = Path(Path.cwd(), 'ants', 'config_templates')
path_connection = Path(Path.cwd(), 'ants', 'connection_data')
path_default = Path(Path.cwd(), 'ants', 'default_configs')

class BaseSSHPexpect:
    def __init__(self, **device_data):
        self.ip = device_data["ip"]
        self.login = device_data["login"]
        self.password = device_data["password"]
        self.root_password = device_data["root_password"]
        self.promt = "[\$#]"

        logging.info(f">>>>> Connection {self.ip}")
        try: 
            self.ssh = pexpect.spawn(f"ssh {self.login}@{self.ip}", timeout=30, encoding="utf-8")
            logging.info(f"Connected {self.ip}")
            self.ssh.expect("[Pp]assword:")
            self.ssh.sendline(self.password)
            self.ssh.expect(self.promt)
            self.ssh.sendline(" ")
            self.ssh.expect(self.promt)
            logging.info(f"Authentication is successful")

        except pexpect.exceptions.TIMEOUT as error:
            logging.error(f"Failed to connect to {self.ip}")

    def send_commands(self, commands):
        result = ""
        logging.info(">>>>> Send config commands")
        for command in commands:
            self.ssh.sendline(command)
            index = self.ssh.expect(self.promt)
            result = result + self.ssh.before
            print(result)
            return result

    def send_show_command(self, command):
        logging.info(">>>>> Send show command")
        self.ssh.sendline(command)
        self.ssh.expect(self.promt)
        result = self.ssh.before
        logging.info("Result") 
        print(result)
        #return result

    def close(self):
        self.ssh.close()
        logging.info(f"<<<<< Close connection {self.ip}")
    
class BaseSSHParamiko:
    def __init__(self, **device_data):
        self.ip = device_data["ip"]
        self.login = device_data["login"]
        self.password = device_data["password"]
        self.root_password = device_data["root_password"]
        self.short_sleep = 0.2
        self.long_sleep = 1
        self.max_read = 10000

        logging.info(f">>>>> Connection to {self.ip} as {self.login}")
        try: 
            self.cl = paramiko.SSHClient()
            self.cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.cl.connect(
                 hostname=self.ip,
                 username=self.login,
                 password=self.password,
                 look_for_keys=False,
                 allow_agent=False,
                 timeout=30
            )
            logging.info("Authentication is successful")

            self._shell = self.cl.invoke_shell()
            time.sleep(self.short_sleep)
            self._shell.recv(self.max_read)
            self.change_to_root()
            self.promt = self._get_promt()

        except socket.timeout as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")

    def _get_promt(self):
        time.sleep(self.short_sleep)
        self._shell.send("\n")
        time.sleep(self.short_sleep)
        output = self.formatting_output()
        match = re.search(r".+[\$#]", output)
        if match:
            return match.group()
        else:
            return "\$"
    
    def formatting_output(self):
        return self._shell.recv(self.max_read).decode("utf-8").replace("\r\n", "\n")
   
    def _output_without_regex(self, command, promt):
        output = self.formatting_output()
        regex =  command + r"(.+)"
        match = re.search(regex, output, re.DOTALL)
        if match:
            print("no match")
            return match.groups()[0]
        return output.replace("\r\n", "\n")
    
    def _send_line_shell(self, command):
        return self._shell.send(f"{command}\n")
    
    def send_shell_show_commands(self, commands, print_output=True):
        time.sleep(self.long_sleep)
        logging.info(f"Send shell show command(s): {commands}")
        try:
            if type(commands) == str:
                self._send_line_shell(commands)
                output = self.formatting_output()
            else:
                output = ""
                for command in commands:
                    self._send_line_shell(command)
                    time.sleep(self.long_sleep)
                    output += self.formatting_output()
        except paramiko.SSHException as error:
            logging.error(f"Возникила ошибка {error} на {self.ip}")
        if print_output:
            return output
  
    def change_to_root(self):
        logging.info(f"Change privileges to root")
        try:
           self._send_line_shell("su -")
           time.sleep(self.long_sleep)
           self._send_line_shell(f"{self.root_password}")
           time.sleep(self.short_sleep)
        except paramiko.SSHException as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")

#-----------------------------Exec commands----------------------------#          
    def send_exec_commands(self, commands, print_output=True):
        logging.info(f"Send exec show command(s): {commands}")
        try:
            if type(commands) == str:
                stdin, stdout, stderr = self.cl.exec_command(commands)
                result = stdout.read().decode("utf-8").replace("\r\n", "\n")
            else:
                result = ""
                for command in commands:
                    stdin, stdout, stderr = self.cl.exec_command(command)
                    result += stdout.read().decode("utf-8").replace("\r\n", "\n") + '\n'
        except paramiko.SSHException as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")
        if print_output:
            return result

    def close(self):
        self.cl.close()
        logging.info(f"<<<<< Close connection {self.ip}")


class SFTPParamiko(BaseSSHParamiko):
    def __init__(self, **device_data):
        super().__init__(**device_data)
        try:
            self.sftp_cl = self.cl.open_sftp()
            logging.info(f"SFTP was opened")
        except socket.timeout as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")

    def read_file(self, file_path):
        try:
            logging.info(f"Чтение файла {file_path}")
            remote_file = self.sftp_cl.open(file_path)
            result = remote_file.read().decode("utf-8").replace('\r\n', '\n')
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"Возникла ошибка {error} при работе с файлом {file_path}")
        finally:
            remote_file.close()
        return result

    def add_to_file(self, content, file_path):
        try:
            logging.info(f"Работа с файлом {file_path}")
            remote_file =self.sftp_cl.open(file_path, mode="a")
            result = remote_file.write(content)
            logging.info(f"Интерфейс добавлен в файл {file_path}")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"Возникла ошибка {error} при работе с файлом {file_path}")
        finally:
            remote_file.close()
            logging.info(f"Закрытие файла")

    def overwrite_file(self, content, file_path):
        try:
            logging.info(f"Работа с файлом {file_path}")
            remote_file =self.sftp_cl.open(file_path, mode="w+")
            result = remote_file.write(content)
            logging.info(f"Файл {file_path} изменен")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"Возникла ошибка {error} при работе с файлом {file_path}")
        finally:
            remote_file.close()
            logging.info(f"Закрытие файла")

    def close(self):
        self.sftp_cl.close()
        logging.info(f"<<<<< Close SFTP connection {self.ip}")

#-----------------------------Добавление подинтерфейсов----------------------------#
def template_network_config_file(device):
    env = Environment(loader=FileSystemLoader(path_config), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("change_net_config_file.txt")
    return template.render(device)

def check_network_config_file(network_params, content):
    logging.info("Проверка сетевых интерфейсов устройства")

    intf_vlan_content = re.findall(r'auto (\S+\d)\.(\d+)', content)
    ip_content = re.findall(r"address (\S+)", content)

    intf_vlan_network = (network_params["interface"], f"{network_params['vlan']}")
    ip_network = network_params["ip"]

    if ip_network in ip_content:
        logging.error(f"IP-адрес {ip_network} уже настроен на устройстве")
    elif intf_vlan_network in intf_vlan_content:
        logging.error(f"Подинтерфейс {intf_vlan_network} уже настроен на устройстве")
    else:
        logging.info(f"IP-адрес {ip_network} и подинтерфейс {intf_vlan_network} свободны")
        template_network_config = template_network_config_file(network_params)
        return template_network_config
    return False

def setup_network_config_file(cl_SSH, cl_SFTP, network_params_for_test):
    file_path = network_params_for_test["path"]
    file_content = cl_SFTP.read_file(file_path)
    template = check_network_config_file(network_params_for_test, file_content)
    if template:
        logging.info("Настройка подинтерфейса на устройстве")
        cl_SFTP.add_to_file(template, file_path)
        cl_SSH.send_setup_command("sudo systemctl restart networking.service")

#-----------------------------Сброс файла в дефолт----------------------------#
def default_template_network_config_file(management_device):
    env = Environment(loader=FileSystemLoader(path_default), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("rpi_config_template.txt")
    return template.render(management_device)

def default_network_config_file(ssh_client, sftp_client, mngmt_params, file_path):
    content = default_template_network_config_file(mngmt_params)
    sftp_client.overwrite_file(content, file_path)
    ssh_client.send_setup_command("sudo systemctl restart networking.service")


if __name__ == "__main__":
    with open(f"{path_connection}/devices.yaml") as file:
        devices  = yaml.safe_load(file)
    
    ssh_con = SFTPParamiko(**devices["ssfp1"])
    print(ssh_con.read_file("/etc/network/interfaces.d/gbe"))
    ssh_con.add_to_file("#", "/etc/network/interfaces.d/gbe")
    print(ssh_con.read_file("/etc/network/interfaces.d/gbe"))
    ssh_con.close()
 

    
    