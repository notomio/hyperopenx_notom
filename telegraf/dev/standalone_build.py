"""Build the software release in a local SlapOS standalone, without any master.

Run with: /opt/slapos/bin/py standalone_build.py <base-dir> <software.cfg>
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
slap.format(4, '127.0.0.1', '::1')
slap.supply(software_url)
try:
  slap.waitForSoftware(max_retry=0, debug=True)
except Exception:
  print('BUILD FAILED')
  raise
print('BUILD OK')
