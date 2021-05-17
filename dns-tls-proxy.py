import asyncio
import logging
import ssl

FORMAT = "%(asctime)s %(name)-4s %(process)d %(levelname)-6s %(funcName)-8s %(message)s"
BIND_ADDRESS = '0.0.0.0'
BIND_PORT = 5353
UPSTREAM_ADDRESS = '1.1.1.1'
UPSTREAM_PORT = 853

logger = logging.getLogger(__name__)


async def query_upstream_server(raw_data):
    """Query a DNS-over-TLS backend server with the given data."""

    # open_connection will create a SSL socket and perform the handshake with upstream server
    reader, writer = await asyncio.open_connection(
        UPSTREAM_ADDRESS, UPSTREAM_PORT, ssl=ssl.create_default_context())

    logger.debug("Quering upstream server with %r", raw_data)
    writer.write(raw_data)

    result = await reader.read(1024)
    logger.debug("Received response from upstream (%s:%s): %r", UPSTREAM_ADDRESS, UPSTREAM_PORT, result)

    logger.debug('Close the connection with backend')
    writer.close()
    await writer.wait_closed()
    return result


async def handle_dns_query(reader, writer):
    data = await reader.read(1024)
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

    server = await asyncio.start_server(handle_dns_query, BIND_ADDRESS, BIND_PORT)
    addr = server.sockets[0].getsockname()
    logger.info("DNS-over-TLS proxy started. listening on %s", addr)

    async with server:
        await server.serve_forever()

asyncio.run(main())