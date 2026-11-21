"""Destroy the instance requested by standalone_instance.py.

Run with: /opt/slapos/bin/py standalone_destroy.py <base-dir> <software.cfg>
"""
import sys
import slapos.slap.standalone

base_dir, software_url = sys.argv[1:3]
slap = slapos.slap.standalone.StandaloneSlapOS(
  base_directory=base_dir,
  server_ip='127.0.0.1',
  server_port=50000,
  local_software_release_root='/')
slap.start()
slap.request(
  software_release=software_url,
  partition_reference='telegraf-test',
  software_type='default',
  state='destroyed')
slap.waitForInstance(max_retry=3)
print('DESTROYED')
