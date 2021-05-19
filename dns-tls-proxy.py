import asyncio
import logging
import os
import socket
import ssl

import aioprometheus

BIND_ADDRESS = os.getenv('BIND_ADDRESS', '0.0.0.0')
BIND_PORT = os.getenv('BIND_PORT', '53')
METRICS_PORT = os.getenv('METRICS_PORT', '5000')
UPSTREAM_ADDRESS = os.getenv('UPSTREAM_ADDRESS', '1.1.1.1')
UPSTREAM_PORT = 853
DEBUG = os.getenv('DEBUG', 0)

FORMAT = "%(asctime)s %(name)-4s %(process)d %(levelname)-6s %(funcName)-8s %(message)s"
logger = logging.getLogger(__name__)


const_labels = {
    "host": socket.gethostname(),
}
REQUESTS = aioprometheus.Counter("requests", "Number of requests.", const_labels=const_labels)
REQUEST_TIME = aioprometheus.Summary("request_processing_seconds", "Time spent processing request",
                                     const_labels=const_labels)
metric_svc = aioprometheus.Service()
metric_svc.register(REQUESTS)
metric_svc.register(REQUEST_TIME)


async def query_upstream_server(raw_data):
    """Query a DNS-over-TLS backend server with the given data."""

    # To establish a SSL/TLS connection not vulnerable to man-in-the-middle attacks,
    # it's essential to make sure the server presents the right certificate.
    # The certificate's hostname-specific data should match the server hostname.
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    # open_connection will create a SSL socket and perform the handshake with upstream server
    reader, writer = await asyncio.open_connection(UPSTREAM_ADDRESS, UPSTREAM_PORT, ssl=ctx)

    logger.debug("Quering upstream server with %r", raw_data)
    writer.write(raw_data)

    result = await reader.read(1024)
    logger.debug("Received response from upstream (%s:%s): %r", UPSTREAM_ADDRESS, UPSTREAM_PORT, result)

    logger.debug('Close the connection with upstream')
    writer.close()
    await writer.wait_closed()

    return result


@aioprometheus.timer(REQUEST_TIME)
async def handle_dns_query(reader, writer):
    data = await reader.read(1024)
    REQUESTS.inc(const_labels)
    addr = writer.get_extra_info('peername')
    logger.info("New query from %s", addr)
    logger.debug("Query data: %r", data)

    result = await query_upstream_server(data)

    writer.write(result)
    await writer.drain()
    logger.info("Close the connection with %s", addr)
    writer.close()


async def main():
    logging.basicConfig(format=FORMAT)

    logger = logging.getLogger(__name__)
    log_level = logging.DEBUG if DEBUG else logging.INFO
    logger.setLevel(log_level)


    logger.info("Starting DNS-over-TLS proxy")
    server = await asyncio.start_server(handle_dns_query, BIND_ADDRESS, BIND_PORT)
    addr = server.sockets[0].getsockname()

    await metric_svc.start(addr=BIND_ADDRESS, port=METRICS_PORT)
    REQUESTS.set(const_labels, 0)

    logger.info("Started DNS-over-TLS proxy, listening on %s, metrics available on %s",
                addr, metric_svc.metrics_url)

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
