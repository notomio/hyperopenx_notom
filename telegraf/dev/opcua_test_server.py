"""OPC UA test server: ns=2;s=Counter increments every second."""
import asyncio
from asyncua import Server, ua


async def main():
  server = Server()
  await server.init()
  server.set_endpoint('opc.tcp://127.0.0.1:48400/test')
  server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
  idx = await server.register_namespace('http://notom.test/telegraf')
  node = await server.nodes.objects.add_variable(
    ua.NodeId('Counter', idx), 'Counter', 0)
  async with server:
    value = 0
    while True:
      await asyncio.sleep(1)
      value += 1
      await node.write_value(value)


asyncio.run(main())
