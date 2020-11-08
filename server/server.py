import socket
import paramiko
import threading
import sys
import threading
import select
import time

#script args
server_address = "0.0.0.0"
clients_port = int(sys.argv[1])
clients_password = sys.argv[2]
contr_port = int(sys.argv[3])
contr_username = "controller"
contr_password = sys.argv[4]
server_host_key = paramiko.RSAKey(filename="./ssh_server.key")

class ContrServer(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()
    def check_auth_password(self, username, password):
        if username == contr_username and password == contr_password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

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

class Client:
    def __init__(self, username, ssh_session, ssh_channel):
        self.username = username
        self.ssh_session = ssh_session
        self.ssh_channel = ssh_channel

class Clients(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.connected = []
        self.clients_socket = None

    def run(self):
        global server_address, clients_port
        self.clients_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #ssh server bind and listen
        try:
            self.clients_socket.bind((server_address, clients_port))
        except:
            print(f"[!] Bind Error for Client SSH Server using {server_address}:{self.clients_socket.getsockname()[1]}")
            sys.exit(1)
        print(f"[*] Bind Success for Client SSH Server using {server_address}:{self.clients_socket.getsockname()[1]}")
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
        client_ssh_session.add_server_key(server_host_key)
        client_server = ClientServer()
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

    def get_client_path(self, client_no):
        client = self.connected[client_no]
        if not client.ssh_channel.closed:
            client.ssh_channel.send("getdir")
            return client.ssh_channel.recv(1024).decode('utf-8').strip()
        return ''

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

class Controller(threading.Thread):
    def __init__(self, clients):
        threading.Thread.__init__(self)
        self.ssh_session = None
        self.contrs_socket = None
        self.clients = clients

    def run(self):
        self.contrs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.contrs_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #ssh server bind and listen
        try:
            self.contrs_socket.bind((server_address, contr_port))
        except:
            print(f"[!] Bind Error for Controller SSH Server using {server_address}:{self.contrs_socket.getsockname()[1]}")
            sys.exit(1)
        print(f"[*] Bind Success for Controller SSH Server using {server_address}:{self.contrs_socket.getsockname()[1]}")
        self.contrs_socket.listen(100)
        print("[*] Listening for Controller")

        while True:
            try:
                self.connect()
            except Exception as err:
                print("[!] Caught Exception: ", type(err), str(err))
                self.exit_controller_session()
                sys.exit(1)

    def connect(self):
        while not select.select([self.contrs_socket], [], [], 1)[0]:
            pass
        contr_socket, addr = self.contrs_socket.accept()
        print(f"[*] Incoming Controller TCP Connection from {addr[0]}:{addr[1]}")
        self.ssh_session = paramiko.Transport(contr_socket)
        self.ssh_session.add_server_key(server_host_key)
        contr_server = ContrServer()
        #start the ssh server and negotiate ssh params
        try:
            self.ssh_session.start_server(server=contr_server)
        except paramiko.SSHException as err:
            self.ssh_session.close()
            print("[!] Controller SSH Parameters Negotiation Failed")
        print("[*] Controller SSH Parameters Negotiation Succeeded")
        #authenticate the controller
        print("[*] Authenticating Controller")
        contr_ssh_channel = self.ssh_session.accept(20)
        if contr_ssh_channel == None or not contr_ssh_channel.active:
            print("[*] SSH Controller Authentication Failure")
            self.exit_controller_session()
        else:
            print("[*] SSH Controller Authenticated")
            try:
                self.handler(contr_ssh_channel)
                self.exit_controller_session()
            except OSError as err:
                if str(err) != "Socket is closed": raise
                print("[*] Controller Disconnected")

    def handler(self, contr_ssh_channel):
        while not contr_ssh_channel.closed:
            command = contr_ssh_channel.recv(1024).decode('utf-8').split(" ")
            if command[0] == "getdir" and len(command[1]):
                try: contr_ssh_channel.send(self.clients.get_client_path(int(command[1])))
                except IndexError:
                    contr_ssh_channel.send("[SERVER] Invalid Client\n")
            elif command[0] == "quit":
                self.exit_controller_session()
                return
            elif command[0] == "ping":
                contr_ssh_channel.send("[SERVER] pong")
            else:
                contr_ssh_channel.send("[SERVER] Invalid command")

    def exit_controller_session(self):
        try:
            if self.ssh_session:
                self.ssh_session.close()
        except:
            print("[!] Error closing Controller SSH session")
        self.ssh_session = None
        print("[*] Controller SSH session closed")


if __name__ == "__main__":
    client_thread = Clients()
    client_thread.daemon = True
    client_thread.start()
    contr_thread = Controller(client_thread)
    contr_thread.daemon = True
    contr_thread.start()
    while contr_thread.is_alive:
        try:
            time.sleep(.1)
        except KeyboardInterrupt:
            client_thread.exit_client_sessions()
            contr_thread.exit_controller_session()
            sys.exit()