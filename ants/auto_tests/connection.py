#!/usr/bin/env -B python3
# -*- coding: utf-8 -*-
import logging
import re
import socket
import time
from typing import List, Any

from paramiko.client import SSHClient, AutoAddPolicy
from paramiko.ssh_exception import AuthenticationException, SSHException, BadHostKeyException
import paramiko
import pexpect
from rich.logging import RichHandler
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    format="{message}",
    datefmt="%H:%M:%S",
    style="{",
    level=logging.DEBUG,
    handlers=[RichHandler()]
)

class ErrorInConnectionException(Exception):
    pass


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
            logging.info("Authentication is successful")
        except pexpect.exceptions.TIMEOUT as error:
            logging.error(f"Failed to connect to {self.ip} - {error}")

    def send_commands(self, commands):
        result = ""
        logging.info(">>>>> Send config commands")
        for command in commands:
            self.ssh.sendline(command)
            self.ssh.expect(self.promt)
            result = result + self.ssh.before
            print(result)
            return result

    def send_show_command(self, command):
        logging.info(">>>>> Send show command")
        self.ssh.sendline(command)
        self.ssh.expect(self.promt)
        result = self.ssh.before
        logging.info("Result")
        return result

    def close(self):
        self.ssh.close()
        logging.info(f"<<<<< Close connection {self.ip}")


class BaseSSHParamiko:
    def __init__(self, **device_data):
        self.ip = device_data["ip"]
        self.login = device_data["login"]
        self.password = device_data["password"]
        try:
            self.root_password = device_data["root_password"]
        except KeyError:
            self.root_password = None
        self.short_sleep = 0.2
        self.long_sleep = 2
        self.max_read = 100000

        logging.info(f">>>>> Connection to {self.ip} as {self.login}")
        try:
            self.cl = SSHClient()
            self.cl.set_missing_host_key_policy(AutoAddPolicy())
            self.cl.connect(
                hostname=self.ip,
                username=self.login,
                password=self.password,
                look_for_keys=False,
                allow_agent=False,
                timeout=30,
                # disabled_algorithms={'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']}
            )
            logging.info("Authentication is successful")

            self._shell = self.cl.invoke_shell()
            time.sleep(self.short_sleep)
            self._shell.recv(self.max_read)
            if self.root_password:
                self._change_to_root()
            self.promt = self._get_promt()
        except (socket.timeout, socket.error) as error:
            logging.critical(f"An error {error} occurred on {self.ip}")
            raise ErrorInConnectionException(error)
        except AuthenticationException as error:
            logging.critical("Authentication failed, please verify your credentials")
            raise ErrorInConnectionException(error)
        except BadHostKeyException as error:
            logging.critical(f"Unable to verify server's host key: {error}")
            raise ErrorInConnectionException(error)
        except SSHException as error:
            logging.critical(f"Unable to establish SSH connection: {error}")
            raise ErrorInConnectionException(error)

    def _get_promt(self):
        time.sleep(self.short_sleep)
        self._shell.send("\n")
        time.sleep(self.short_sleep)
        output = self._formatting_output()
        match = re.search(r".+[\$#]", output)
        if match:
            return match.group()
        else:
            return "\$"

    def _formatting_output(self):
        return self._shell.recv(self.max_read).decode("utf-8").replace("\r\n", "\n")

    def _send_line_shell(self, command):
        return self._shell.send(f"{command}\n")

    def send_shell_commands(self, commands, print_output=True):
        time.sleep(self.long_sleep)
        logging.info(f">>> Send shell command(s) on {self.ip}: {commands}")
        try:
            if type(commands) == str:
                self._send_line_shell(commands)
                time.sleep(self.long_sleep)
                output = self._formatting_output()
            else:
                output = ""
                for command in commands:
                    self._send_line_shell(command)
                    time.sleep(self.long_sleep)
                    output += self._formatting_output()
            if print_output:
                return output
        except paramiko.SSHException as error:
            logging.error(f"An error {error} occurred on {self.ip}")

    def _change_to_root(self):
        logging.info("Change privileges to root")
        try:
            self._send_line_shell("su -")
            time.sleep(self.long_sleep)
            self._send_line_shell(f"{self.root_password}")
            time.sleep(self.short_sleep)
        except paramiko.SSHException as error:
            logging.error(f"An error {error} occurred on {self.ip}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.cl.close()
        logging.info(f"<<<<< Close connection {self.ip}")

    # -----------------------------Exec commands----------------------------#
    def send_exec_commands(self, commands, print_output=True):
        logging.info(f">>> Send exec show command(s) on {self.ip}: {commands}")
        try:
            result = ""
            if type(commands) == str:
                stdin, stdout, stderr = self.cl.exec_command(commands)
                if print_output:
                    result = stdout.read().decode("utf-8").replace("\r\n", "\n")
            else:
                for command in commands:
                    stdin, stdout, stderr = self.cl.exec_command(command)
                    if print_output:
                        result += stdout.read().decode("utf-8").replace("\r\n", "\n") + '\n'
            if print_output:
                return result
        except paramiko.SSHException as error:
            logging.error(f"An error {error} occurred on {self.ip}")


class SFTPParamiko:
    def __init__(self, **device_data):
        self.ip = device_data["ip"]
        self.login = device_data["login"]
        self.root_password = device_data["root_password"]

        logging.info(f">>>>> Connection to {self.ip} with root")
        try:
            self.root_cl = SSHClient()
            self.root_cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.root_cl.connect(
                hostname=self.ip,
                username="root",
                password=self.root_password,
                look_for_keys=False,
                allow_agent=False,
                timeout=30
            )
            logging.info("Authentication as root is successful")
            self.sftp_cl = self.root_cl.open_sftp()
            logging.info("SFTP was opened")
        except socket.timeout as error:
            logging.critical(f"An error {error} occurred on {self.ip}")
            raise ErrorInConnectionException(error)
        except AuthenticationException as error:
            logging.critical("Authentication failed, please verify your credentials")
            raise ErrorInConnectionException(error)
        except BadHostKeyException as error:
            logging.critical(f"Unable to verify server's host key: {error}")
            raise ErrorInConnectionException(error)
        except SSHException as error:
            logging.critical(f"Unable to establish SSH connection: {error}")
            raise ErrorInConnectionException(error)

    # -----------------------------File actions----------------------------#
    def read_file(self, file_path):
        try:
            logging.info(f"Read the file {file_path}")
            remote_file = self.sftp_cl.open(file_path)
            result = remote_file.read().decode("utf-8").replace('\r\n', '\n')
            remote_file.close()
            return result
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error {error} while working with the file {file_path}")

    def add_to_file(self, content, file_path):
        try:
            logging.info(f"Opening a file {file_path}")
            remote_file = self.sftp_cl.open(file_path, mode="a")
            remote_file.write(content)
            logging.info(f"Interface added to file {file_path}")
            remote_file.close()
            logging.info(f"File {file_path} closed successfully")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error {error} while working with the file {file_path}")

    def overwrite_file(self, content, file_path):
        try:
            logging.info(f"Open the file {file_path}")
            remote_file = self.sftp_cl.open(file_path, mode="w+")
            remote_file.write(content)
            logging.info(f"The file {file_path} have changed")
            remote_file.close()
            logging.info(f"File {file_path} closed successfully")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error {error} while working with the file {file_path}")

    def put_file(self, local_path, remote_path):
        """
        Должен передаваться полный путь
        """
        try:
            logging.info(f"Put {local_path} on {self.ip}")
            logging.debug(f"Local path: {local_path}, remote path: {remote_path}")
            # sftp.put returns "IOError: Failure" if the path name is a directory.
            # Therefore, need to add a filename to the directory.
            # https://github.com/paramiko/paramiko/issues/1000?ysclid=lg51z5k5nz705979083
            if isinstance(local_path, Path):
                self.sftp_cl.put(local_path, f"{remote_path}/{local_path.name}")
                logging.info(f"File {local_path} has been copied to path {remote_path}")
            else:
                logging.error(f"Wrong type of local path - {type(local_path)} instead Path")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error - '{error}' while working with the file {local_path}")

    # -----------------------------Path actions----------------------------#
    def change_dir(self, dir_path):
        try:
            logging.info(f"Change directory to {dir_path}")
            return self.sftp_cl.chdir(dir_path)
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error: '{error}' while working with the directory {dir_path}")

    def get_cwd(self):
        try:
            logging.info(f"Get current directory: {self.sftp_cl.getcwd()}")
            return self.sftp_cl.getcwd()
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error {error} while working with the file {self.sftp_cl.getcwd()}")

    def mkdir(self, remote_path):
        try:
            logging.info(f"Create directory: {remote_path}")
            self.sftp_cl.mkdir(remote_path)
            logging.debug(f"Directory {remote_path} created successfully")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error - '{error}' while working with the file {remote_path}")

    def list_dir(self):
        try:
            logging.info(f"List directory: {self.sftp_cl.listdir()}")
            return self.sftp_cl.listdir()
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"There was an error - '{error}' while working with the file {self.sftp_cl.listdir()}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.root_cl.close()
        logging.info(f"<<<<< Close SFTP connection {self.ip}")


class ScanDevices:
    def __init__(self, devices_connection_data, test_devices):
        test_device_list = []
        self.params_list = []

        for dev in test_devices:
            self.params_list.append(devices_connection_data[dev])

    def _scan_device(self, device_params):
        ip_address = device_params["ip"]
        logging.info(f"Scanning device {ip_address} for test")
        try:
            with SSHClient() as ssh:
                ssh.set_missing_host_key_policy(AutoAddPolicy())
                ssh.connect(
                    hostname=ip_address,
                    username=device_params["login"],
                    password=device_params["password"],
                    look_for_keys=False,
                    allow_agent=False,
                    timeout=30
                )
                logging.info(f"Authentication on {ip_address} successful")
                return True
        except (socket.timeout, paramiko.SSHException, OSError) as error:
            logging.error(f"An error {error} occurred on {ip_address}")
            return False

    def scan_devices(self, limit=10):
        scan_success = []
        scan_fail = []
        with ThreadPoolExecutor(max_workers=limit) as executor:
            result = executor.map(self._scan_device, self.params_list)
            for device, status in zip(self.params_list, result):
                if status:
                    scan_success.append(device["ip"])
                else:
                    scan_fail.append(device["ip"])
            return scan_success, scan_fail
