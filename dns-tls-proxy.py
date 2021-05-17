import asyncio
import logging
import socket
import ssl
import uuid

import aioprometheus

FORMAT = "%(asctime)s %(name)-4s %(process)d %(levelname)-6s %(funcName)-8s %(message)s"
BIND_ADDRESS = '0.0.0.0'
BIND_PORT = 5353
UPSTREAM_ADDRESS = '1.1.1.1'
UPSTREAM_PORT = 853

logger = logging.getLogger(__name__)

const_labels = {
    "host": socket.gethostname(),
}

REQUESTS = aioprometheus.Counter("requests", "Number of requests.", const_labels=const_labels)
REQUEST_TIME = aioprometheus.Summary("request_processing_seconds", "Time spent processing request",
                                     const_labels=const_labels)

msvc = aioprometheus.Service()
msvc.register(REQUESTS)
msvc.register(REQUEST_TIME)


async def query_upstream_server(raw_data):
    """Query a DNS-over-TLS backend server with the given data."""

    # open_connection will create a SSL socket and perform the handshake with upstream server
    reader, writer = await asyncio.open_connection(
        UPSTREAM_ADDRESS, UPSTREAM_PORT, ssl=ssl.create_default_context())

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
    logger.setLevel(logging.DEBUG)
    logger.info("Starting DNS-over-TLS proxy")

    await msvc.start(addr='0.0.0.0', port=5000)
    REQUESTS.set(const_labels, 0)

    server = await asyncio.start_server(handle_dns_query, BIND_ADDRESS, BIND_PORT)
    addr = server.sockets[0].getsockname()
    logger.info("DNS-over-TLS proxy started. listening on %s", addr)

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
