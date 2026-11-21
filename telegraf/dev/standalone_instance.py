"""Request an instance of the software release in the local SlapOS standalone.

Run with: /opt/slapos/bin/py standalone_instance.py <base-dir> <software.cfg> <parameters.json>
"""
import json
import sys
import slapos.slap
import slapos.slap.standalone

base_dir, software_url, parameter_file = sys.argv[1:4]
with open(parameter_file) as f:
  parameters = f.read()
json.loads(parameters)

slap = slapos.slap.standalone.StandaloneSlapOS(
  base_directory=base_dir,
  server_ip='127.0.0.1',
  server_port=50000,
  local_software_release_root='/')
slap.start()
slap.format(4, '127.0.0.1', '::1')
slap.supply(software_url)
partition = slap.request(
  software_release=software_url,
  partition_reference='telegraf-test',
  partition_parameter_kw={'_': parameters},
  software_type="default")
try:
  slap.waitForInstance(max_retry=3)
except Exception:
  print('INSTANCE FAILED')
  raise
partition = slap.request(
  software_release=software_url,
  partition_reference='telegraf-test',
  partition_parameter_kw={'_': parameters},
  software_type="default")
print('INSTANCE OK')
print(json.dumps(partition.getConnectionParameterDict(), indent=2))
