# Development scripts

Helpers to test the software release in a local SlapOS standalone, without a
SlapOS master. They are not part of the software release.

Run them with the Python of a SlapOS node, for example
`/opt/slapos/bin/py script.py ...`.

| File | Use |
| --- | --- |
| `standalone_build.py` | Build `software.cfg` in a standalone. |
| `standalone_instance.py` | Request an instance with a JSON parameter file. |
| `standalone_destroy.py` | Destroy the instance of `standalone_instance.py`. |
| `params-basic.json`, `params-opcua-mqtt.json` | Example instance parameters. |
| `opcua_test_server.py` | OPC UA server for manual tests (port 48400). |
| `supervisord`, `supervisorctl` | Wrappers for a node whose eggs hold `supervisor` but no executable. |
| `nxdbom` | Stand-in for `nxdbom` on a machine without `slapos-sr-testing`. It writes an empty SBOM. |
