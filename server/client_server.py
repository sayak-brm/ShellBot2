import paramiko
import threading
import socket
import sys
import select

#ssh server parameters defined in the class
class ClientServer(paramiko.ServerInterface):
    def __init__(self, clients_password):
        self.event = threading.Event()
        self.username = ""
        self.clients_password = clients_password
    def check_auth_password(self, username, password):
        if password == self.clients_password:
            self.username = username
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

class Client:
    def __init__(self, username, ssh_session, ssh_channel):
        self.username = username
        self.ssh_session = ssh_session
        self.ssh_channel = ssh_channel

class Clients(threading.Thread):
    def __init__(self, server_address, clients_port, clients_password, server_host_key):
        threading.Thread.__init__(self)
        self.connected = []
        self.clients_socket = None
        self.server_address = server_address
        self.clients_port = clients_port
        self.clients_password = clients_password
        self.server_host_key = server_host_key

    def run(self):
        self.clients_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #ssh server bind and listen
        try:
            self.clients_socket.bind((self.server_address, self.clients_port))
        except:
            print(f"[!] Bind Error for Client SSH Server using {self.server_address}:{self.clients_socket.getsockname()[1]}")
            sys.exit(1)
        print(f"[*] Bind Success for Client SSH Server using {self.server_address}:{self.clients_socket.getsockname()[1]}")
        self.clients_socket.listen(100)
        print("[*] Listening for incoming client connections")

        #Keep ssh server active and accept incoming tcp connections
        while True:
            try:
                self.handle_clients()
            except Exception as err:
                print("[*] Caught Exception while handling Clients: ", type(err), str(err))
                self.exit_client_sessions()
                sys.exit(1)
    
    def handle_clients(self):
        while not select.select([self.clients_socket], [], [], 1)[0]:
            pass
        client_socket, addr = self.clients_socket.accept()
        print(f"[*] Incoming Client TCP Connection from {addr[0]}:{addr[1]}")
        client_ssh_session = paramiko.Transport(client_socket)
        client_ssh_session.add_server_key(self.server_host_key)
        client_server = ClientServer(self.clients_password)
        # start the ssh server and negotiate ssh params
        try:
            client_ssh_session.start_server(server=client_server)
        except paramiko.SSHException:
            client_ssh_session.close()
            # print("[!] SSH Parameters Negotiation Failed")
        # print("[*] SSH Parameters Negotiation Succeeded")
        # authenticate the client
        # print("[*] Authenticating")
        client_ssh_channel = client_ssh_session.accept(20)
        if client_ssh_channel == None or not client_ssh_channel.active:
            # print("[*] SSH Client Authentication Failure")
            client_ssh_session.close()
        else:
            print(f"[*] Client Authenticated with username: {client_server.username}")
            client = Client(client_server.username, client_ssh_session, client_ssh_channel)
            self.connected.append(client)
            # client_handler(0)

    def exit_client_sessions(self):
        for client in self.connected[:]:
            try:
                if not client.ssh_channel.closed:
                    client.ssh_channel.send("quit")
                    client.ssh_session.close()
                self.connected.remove(client)
                print(f"[*] Client SSH session closed for {client.username}")
            except:
                pass
                print(f"[!] Error closing Client SSH session for {client.username}")