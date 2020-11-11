import paramiko
import subprocess
import sys
import time
import platform
import os

#script args
server_address = sys.argv[1]
server_port = int(sys.argv[2])
username = "controller"
password = sys.argv[3]

server_session = None

def exit_server_session():
    global server_session
    if server_session == None: return
    try: server_session.close()
    except OSError: pass
    server_session = None

def get_client_path():
    if server_session == None: return ""
    server_session.send("getdir")
    return server_session.recv(1024).decode('utf-8')

def process_commands():
    while True:
        if server_session == None: return
        command = input(f"S> ").strip()
        if command == "exit":
            server_session.send(command)
            return
        server_session.send(command)
        print(server_session.recv(1024).decode('utf-8'))

#connect to the remote ssh server and recieve commands to be #executed and send back output
def ssh_command(server_address, server_port, username, password):
    global server_session
    #instantiate the ssh client
    server = paramiko.SSHClient()
    #optional is using keys instead of password auth
    #server.load_host_key('/path/to/file')
    #auto add key
    server.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #connect to ssh server
    server.connect(
        server_address,
        port=server_port,
        username=username,
        password=password
    )
    #get ssh session
    server_session = server.get_transport().open_session()
    if server_session.active and not server_session.closed:
        #wait for command, execute and send result ouput
        process_commands()
    exit_server_session()
    return

try:
    ssh_command(server_address, server_port, username, password)
except KeyboardInterrupt:
    exit_server_session()
    sys.exit()
