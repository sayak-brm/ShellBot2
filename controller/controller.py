import paramiko
import subprocess
import sys
import time
import platform
import os

#script args
server_address = sys.argv[1]
server_port = int(sys.argv[2])
username = sys.argv[3]
password = sys.argv[4]

client_session = None

def exit_client_session():
    global client_session
    if client_session == None: return
    client_session.send("quit")
    client_session.close()
    client_session = None

def get_client_path(client_no):
    if client_session == None: return ""
    client_session.send("getdir " + str(client_no))
    return client_session.recv(1024).decode('utf-8')

def process_commands():
    if client_session == None: return
    command = input(f"{get_client_path(0)}:$> ").strip()
    if command == "quit":
        exit_client_session()
        return
    client_session.send(command)
    print(client_session.recv(1024).decode('utf-8'))

#connect to the remote ssh server and recieve commands to be #executed and send back output
def ssh_command(server_address, server_port, username, password):
    global client_session
    #instantiate the ssh client
    client = paramiko.SSHClient()
    #optional is using keys instead of password auth
    #client.load_host_key('/path/to/file')
    #auto add key
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #connect to ssh server
    client.connect(
        server_address,
        port=server_port,
        username=username,
        password=password
    )
    #get ssh session
    client_session = client.get_transport().open_session()
    if client_session.active and not client_session.closed:
        #wait for command, execute and send result ouput
        while True:
            #use subprocess run with timeout of 30 seconds
            process_commands()
    client_session.close()
    return

try:
    ssh_command(server_address, server_port, username, password)
except KeyboardInterrupt:
    exit_client_session()
    sys.exit()
