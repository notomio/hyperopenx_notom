# Tests for the Telegraf software release

The tests build the software release, request instances in a standalone
SlapOS and check the behaviour. They follow `slapos-sr-testing`.

Environment variables of `slapos-sr-testing` apply (`SLAPOS_TEST_IPV4`,
`SLAPOS_TEST_IPV6`, `SLAPOS_TEST_WORKING_DIR`, ...). Two more are read:

| Variable | Description |
| --- | --- |
| `TELEGRAF_TEST_OPCUA_PYTHON` | Python interpreter that can import `asyncua`. Default: the interpreter that runs the tests. The OPC UA tests are skipped when `asyncua` is missing. |
| `TELEGRAF_TEST_OPENSSL` | `openssl` executable used to create test certificates. Default: `openssl`. |

Run all tests from this directory:

```
python -m unittest discover -v
```

The MQTT broker of the tests is a small Python server in `test.py`. It
accepts MQTT 3.1.1 publications and needs no external program.
