# Telegraf software release

Builds Telegraf v1.39.3 with Go 1.26 and runs it in a partition.
The configuration has an OPC UA input and an MQTT output.
Parameters are in `instance-input-schema.json`.

Example request:

```json
{
  "agent": {"hostname": "plc-1"},
  "opcua": {
    "endpoint": "opc.tcp://[::1]:4840",
    "nodes": [{"name": "ServerState", "id": "ns=0;i=2259"}]
  },
  "mqtt": {"servers": ["mqtt://localhost:1883"], "topic": "plc/state"}
}
```

Telegraf does not start without at least one input. Give an `opcua` input
or an input in `extra-config`.

Put extra TOML files in `srv/telegraf.d` of the partition to add plugins.
