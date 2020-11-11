import paramiko
import sys
import time

from client_server import Clients
from controller_server import Controller

#script args
server_address = "0.0.0.0"
clients_port = int(sys.argv[1])
clients_password = sys.argv[2]
contr_port = int(sys.argv[3])
contr_username = "controller"
contr_password = sys.argv[4]
server_host_key = paramiko.RSAKey(filename="./ssh_server.key")

if __name__ == "__main__":
    client_thread = Clients(server_address, clients_port, clients_password, server_host_key)
    client_thread.daemon = True
    client_thread.start()
    contr_thread = Controller(client_thread, server_address, contr_port, contr_username, contr_password, server_host_key)
    contr_thread.daemon = True
    contr_thread.start()
    while contr_thread.is_alive:
        try:
            time.sleep(.1)
        except KeyboardInterrupt:
            client_thread.exit_client_sessions()
            contr_thread.exit_controller_session()
            sys.exit()
