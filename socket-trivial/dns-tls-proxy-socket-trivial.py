import logging
import socket
import ssl

from os import environ
from sys import platform as _platform

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# TLS connection with CloudFlare server
def tls_conn(DNS):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.verify_mode = ssl.CERT_REQUIRED
    # Linux or inside container
    if _platform == "linux":
         context.load_verify_locations('/etc/ssl/certs/ca-certificates.crt')
    # running locally on MacOS
    elif _platform == "darwin":
        home_dir = environ.get('HOME')
        cacert_file = f"{home_dir}/Library/Python/2.7/lib/python/site-packages/certifi/cacert.pem"
        context.load_verify_locations(cacert_file)

    wrapped_socket = context.wrap_socket(sock, server_hostname=DNS)
    wrapped_socket.connect((DNS, 853))
    return wrapped_socket


# handle incoming DNS request
def handle_request(data, addr, TLS_DNS):
    tls_conn_sock = tls_conn(TLS_DNS)
    tls_conn_sock.send(data)
    tcp_result = tls_conn_sock.recv(1024)
    if tcp_result:
        rcode = tcp_result[:6].hex()
        rcode = str(rcode)[11:]
        # Check RCODE field in DNS response
        if int(rcode, 16) == 3:
            logger.info(f"Request from {addr}, target host not found")
        logger.info(f"Request from {addr} served OK")
        return tcp_result
    else:
        logger.error(f"Wrong DNS response from {TLS_DNS}, ignoring")
        return None


if __name__ == '__main__':
    TLS_DNS = '1.1.1.1'
    bind_host = '0.0.0.0'
    bind_port = 53
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((bind_host, bind_port))
        s.listen()
        while True:
            conn, addr = s.accept()
            data = conn.recv(1024)
            result = handle_request(data, addr, TLS_DNS)
            if result:
                conn.sendall(result)
            conn.close()
