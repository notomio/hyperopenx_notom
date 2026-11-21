"""OPC UA test server.

The node ns=2;s=Counter increments every second.

Usage: opcua_server.py PORT [CERTIFICATE PRIVATE_KEY]
Without certificate, the server accepts only unsecured connections.
With a certificate, it accepts only Basic256Sha256 SignAndEncrypt.
"""
import asyncio
import sys

from asyncua import Server, ua


async def main(port, certificate=None, private_key=None):
  server = Server()
  await server.init()
  server.set_endpoint('opc.tcp://127.0.0.1:%s/test' % port)
  server.set_application_uri('urn:telegraf:test:server')
  if certificate:
    await server.load_certificate(certificate)
    await server.load_private_key(private_key)
    server.set_security_policy(
      [ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
  else:
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
  idx = await server.register_namespace('http://notom.test/telegraf')
  node = await server.nodes.objects.add_variable(
    ua.NodeId('Counter', idx), 'Counter', 0)
  async with server:
    print('READY', flush=True)
    value = 0
    while True:
      await asyncio.sleep(1)
      value += 1
      await node.write_value(value)


asyncio.run(main(*sys.argv[1:]))
