#!/usr/bin/env -B python3
# -*- coding: utf-8 -*-
import logging
import re
import socket
import time

import paramiko
import pexpect
from rich.logging import RichHandler
from paramiko import ssh_exception

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
        self.long_sleep = 5
        self.max_read = 100000

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
                 timeout=30, 
                 disabled_algorithms={'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']}
                 )
            logging.info("Authentication is successful")

            self._shell = self.cl.invoke_shell()
            time.sleep(self.short_sleep)
            self._shell.recv(self.max_read)
            self._change_to_root()
            self.promt = self._get_promt()
        except socket.timeout as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")
        except socket.error as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")   

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
   
    def _output_without_regex(self, command, promt):
        output = self._formatting_output()
        regex =  command + r"(.+)"
        match = re.search(regex, output, re.DOTALL)
        if match:
            print("no match")
            return match.groups()[0]
        return output.replace("\r\n", "\n")
    
    def _send_line_shell(self, command): 
        return self._shell.send(f"{command}\n")
    
    def send_shell_commands(self, commands, print_output=True):
        time.sleep(self.long_sleep)
        logging.info(f">>> Send shell command(s): {commands}")
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
        except paramiko.SSHException as error:
            logging.error(f"Возникила ошибка {error} на {self.ip}")
        if print_output:
            return output
  
    def _change_to_root(self):
        logging.info(f"Change privileges to root")
        try:
           self._send_line_shell("su -")
           time.sleep(self.long_sleep)
           self._send_line_shell(f"{self.root_password}")
           time.sleep(self.short_sleep)
        except paramiko.SSHException as error:
            logging.error(f"Возникла ошибка {error} на {self.ip}")

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        
    def close(self):
        self.cl.close()
        logging.info(f"<<<<< Close connection {self.ip}")

#-----------------------------Exec commands----------------------------#          
    def send_exec_commands(self, commands, print_output=True):
        logging.info(f">>> Send exec show command(s): {commands}")
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

class SFTPParamiko():
    def __init__(self, **device_data):
        self.ip = device_data["ip"]
        self.login = device_data["login"]
        self.root_password = device_data["root_password"]

        logging.info(f">>>>> Connection to {self.ip} with root")
        try:
            self.root_cl = paramiko.SSHClient()
            self.root_cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.root_cl.connect(
                        hostname=self.ip,
                        username="root",
                        password=self.root_password,
                        look_for_keys=False,
                        allow_agent=False,
                        timeout=30
                    )
            logging.info(f"Authentication as root is successful")
            try:
                self.sftp_cl = self.root_cl.open_sftp()
                logging.info(f"SFTP was opened")
            except Exception:
                logging.error("Какая-то ошибка")
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
            remote_file = self.sftp_cl.open(file_path, mode="w+")
            result = remote_file.write(content)
            logging.info(f"Файл {file_path} изменен")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"Возникла ошибка {error} при работе с файлом {file_path}")
        finally:
            remote_file.close()
            logging.info(f"Закрытие файла")

    def put_file(self, local_path, remote_path):
        try:
            logging.info(f"Работа с файлом {local_path}")
            self.sftp_cl.put(local_path, remote_path)
            logging.info(f"Файл {local_path} был перенесен по пути {remote_path}")
        except (paramiko.SFTPError, IOError) as error:
            logging.error(f"Возникла ошибка {error} при работе с файлом {remote_path}")

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.sftp_cl.close()
        logging.info(f"<<<<< Close SFTP connection {self.ip}")

