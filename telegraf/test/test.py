import contextlib
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import psutil
import requests

try:
  import tomllib

  def loadToml(path):
    with open(path, 'rb') as f:
      return tomllib.load(f)
except ImportError:  # Python < 3.11
  import toml

  def loadToml(path):
    return toml.load(path)

from slapos.slap.standalone import SlapOSNodeCommandError
from slapos.testing.testcase import makeModuleSetUpAndTestCaseClass

setUpModule, SlapOSInstanceTestCase = makeModuleSetUpAndTestCaseClass(
  os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'software.cfg')))

HERE = os.path.dirname(os.path.abspath(__file__))
OPCUA_PYTHON = os.environ.get('TELEGRAF_TEST_OPCUA_PYTHON', sys.executable)
OPENSSL = os.environ.get('TELEGRAF_TEST_OPENSSL', 'openssl')


def hasAsyncua():
  return subprocess.call(
    [OPCUA_PYTHON, '-c', 'import asyncua'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def freePort():
  with contextlib.closing(socket.socket()) as s:
    s.bind(('127.0.0.1', 0))
    return s.getsockname()[1]


def waitFor(condition, timeout=60, interval=0.5):
  """Return the first truthy result of condition(), or None after timeout."""
  deadline = time.time() + timeout
  while time.time() < deadline:
    result = condition()
    if result:
      return result
    time.sleep(interval)


def makeCertificate(directory, name, uri):
  """Create a self-signed certificate and key. Return the two paths."""
  certificate = os.path.join(directory, name + '-cert.pem')
  key = os.path.join(directory, name + '-key.pem')
  subprocess.check_call([
    OPENSSL, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
    '-keyout', key, '-out', certificate, '-days', '2',
    '-subj', '/CN=' + name,
    '-addext', 'subjectAltName=URI:%s,DNS:localhost,IP:127.0.0.1' % uri,
    '-addext', 'keyUsage=digitalSignature,nonRepudiation,keyEncipherment,'
               'dataEncipherment,keyCertSign',
    '-addext', 'extendedKeyUsage=serverAuth,clientAuth',
  ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return certificate, key


def readFile(path):
  with open(path) as f:
    return f.read()


class FakeMQTTBroker:
  """Minimal MQTT 3.1.1 broker. It stores every publication."""

  def __init__(self):
    self.messages = []  # list of (topic, payload)
    self._lock = threading.Lock()
    self._socket = socket.socket()
    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self._socket.bind(('127.0.0.1', 0))
    self._socket.listen(5)
    self.port = self._socket.getsockname()[1]
    self._stopped = False
    threading.Thread(target=self._accept, daemon=True).start()

  def stop(self):
    self._stopped = True
    self._socket.close()

  def _accept(self):
    while not self._stopped:
      try:
        connection, _ = self._socket.accept()
      except OSError:
        return
      threading.Thread(
        target=self._serve, args=(connection,), daemon=True).start()

  @staticmethod
  def _read(connection, size):
    data = b''
    while len(data) < size:
      chunk = connection.recv(size - len(data))
      if not chunk:
        raise EOFError
      data += chunk
    return data

  def _serve(self, connection):
    with connection:
      try:
        while True:
          first = self._read(connection, 1)[0]
          length = 0
          multiplier = 1
          while True:
            byte = self._read(connection, 1)[0]
            length += (byte & 127) * multiplier
            multiplier *= 128
            if not byte & 128:
              break
          body = self._read(connection, length) if length else b''
          packet_type = first >> 4
          if packet_type == 1:  # CONNECT
            connection.sendall(b'\x20\x02\x00\x00')
          elif packet_type == 3:  # PUBLISH
            qos = (first >> 1) & 3
            topic_length = int.from_bytes(body[:2], 'big')
            topic = body[2:2 + topic_length].decode()
            offset = 2 + topic_length
            packet_id = body[offset:offset + 2]
            if qos:
              offset += 2
            with self._lock:
              self.messages.append((topic, body[offset:]))
            if qos == 1:
              connection.sendall(b'\x40\x02' + packet_id)
            elif qos == 2:
              connection.sendall(b'\x50\x02' + packet_id)
          elif packet_type == 6:  # PUBREL
            connection.sendall(b'\x70\x02' + body[:2])
          elif packet_type == 12:  # PINGREQ
            connection.sendall(b'\xd0\x00')
          elif packet_type == 14:  # DISCONNECT
            return
      except (EOFError, OSError):
        return

  def counters(self, topic):
    """Values of the Counter field published on topic."""
    result = []
    with self._lock:
      messages = list(self.messages)
    for message_topic, payload in messages:
      if message_topic == topic:
        fields = json.loads(payload).get('fields', {})
        if 'Counter' in fields:
          result.append(fields['Counter'])
    return result


class TelegrafTestCase(SlapOSInstanceTestCase):
  """Base class. Subclasses define getParameters().

  The servers started by startBroker and startOPCUAServer stop at the end
  of the class.
  """
  topic = 'plc/counter'

  @classmethod
  def getParameters(cls):
    return {}

  @classmethod
  def getInstanceParameterDict(cls):
    return {'_': json.dumps(cls.getParameters())}

  @classmethod
  def startBroker(cls):
    broker = FakeMQTTBroker()
    cls.addClassCleanup(broker.stop)
    cls.broker = broker
    return broker

  @classmethod
  def startOPCUAServer(cls, certificate=None, key=None):
    port = freePort()
    command = [OPCUA_PYTHON, os.path.join(HERE, 'opcua_server.py'), str(port)]
    if certificate:
      command += [certificate, key]
    process = subprocess.Popen(
      command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
      universal_newlines=True)
    cls.addClassCleanup(process.wait)
    cls.addClassCleanup(process.terminate)
    ready = threading.Event()

    def watch():
      for line in process.stdout:
        if line.startswith('READY'):
          ready.set()

    threading.Thread(target=watch, daemon=True).start()
    if not ready.wait(60):
      raise RuntimeError('OPC UA test server did not start')
    return 'opc.tcp://127.0.0.1:%s/test' % port

  @classmethod
  def makeTemporaryDirectory(cls):
    directory = tempfile.TemporaryDirectory()
    cls.addClassCleanup(directory.cleanup)
    return directory.name

  @property
  def configPath(self):
    return os.path.join(
      str(self.computer_partition_root_path), 'etc', 'telegraf.toml')

  def config(self):
    return loadToml(self.configPath)

  def connectionParameters(self):
    return self.computer_partition.getConnectionParameterDict()

  def telegrafProcesses(self):
    return [
      p for p in psutil.process_iter(['cmdline'])
      if p.info['cmdline'] and self.configPath in p.info['cmdline']
      and os.path.basename(p.info['cmdline'][0]) == 'telegraf']

  def assertHealthy(self):
    url = self.connectionParameters()['health-url']

    def check():
      try:
        return requests.get(url).status_code == 200
      except requests.ConnectionError:
        return False

    self.assertTrue(
      waitFor(check), 'health endpoint %s does not answer 200' % url)

  def assertDataFlow(self, topic=None):
    topic = topic or self.topic
    self.assertTrue(
      waitFor(lambda: self.broker.counters(topic), timeout=90),
      'no OPC UA value reached the MQTT topic %s' % topic)

  def assertPrivateFile(self, path):
    self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600, path)


class TestBasic(TelegrafTestCase):

  @classmethod
  def getParameters(cls):
    return {'extra-config': '[[inputs.cpu]]\n  totalcpu = true\n'}

  def test_service_runs(self):
    self.assertEqual(len(self.telegrafProcesses()), 1)
    self.assertHealthy()

  def test_config_file_is_private(self):
    self.assertPrivateFile(self.configPath)

  def test_default_values(self):
    agent = self.config()['agent']
    self.assertEqual(agent['interval'], '10s')
    self.assertEqual(agent['flush_interval'], '10s')
    self.assertTrue(agent['omit_hostname'])

  def test_extra_config_is_appended(self):
    self.assertEqual(self.config()['inputs']['cpu'], [{'totalcpu': True}])

  def test_no_plugin_without_parameter(self):
    config = self.config()
    self.assertNotIn('opcua', config['inputs'])
    self.assertNotIn('mqtt', config['outputs'])

  def test_published_parameters(self):
    self.assertTrue(os.path.exists(self.connectionParameters()['logfile']))


def opcuaParameters(cls, **opcua):
  """Parameters of an OPC UA to MQTT instance. Starts the servers."""
  broker = cls.startBroker()
  return {
    'agent': {'interval': '1s', 'flush-interval': '1s', 'hostname': 'plc-1'},
    'opcua': dict({
      'nodes': [{'name': 'Counter', 'id': 'ns=2;s=Counter'}],
    }, **opcua),
    'mqtt': {
      'servers': ['mqtt://127.0.0.1:%s' % broker.port],
      'topic': cls.topic,
    },
  }


@unittest.skipUnless(hasAsyncua(), 'asyncua is not available')
class TestOpcuaToMqtt(TelegrafTestCase):

  @classmethod
  def getParameters(cls):
    return opcuaParameters(
      cls,
      endpoint=cls.startOPCUAServer(),
      **{'security-policy': 'None', 'security-mode': 'None'})

  def test_config_matches_parameters(self):
    config = self.config()
    self.assertEqual(config['agent']['hostname'], 'plc-1')
    opcua, = config['inputs']['opcua']
    self.assertEqual(
      opcua['nodes'], [{'name': 'Counter', 'id': 'ns=2;s=Counter'}])
    mqtt, = config['outputs']['mqtt']
    self.assertEqual(mqtt['topic'], self.topic)
    self.assertEqual(mqtt['qos'], 1)

  def test_values_reach_mqtt(self):
    self.assertDataFlow()

  def test_values_increase(self):
    waitFor(lambda: len(self.broker.counters(self.topic)) >= 3, timeout=90)
    values = self.broker.counters(self.topic)
    self.assertGreaterEqual(len(values), 3)
    self.assertGreater(values[-1], values[0])

  def test_health(self):
    self.assertHealthy()


@unittest.skipUnless(hasAsyncua(), 'asyncua is not available')
class TestParameterChange(TelegrafTestCase):

  @classmethod
  def getParameters(cls):
    return opcuaParameters(
      cls,
      endpoint=cls.startOPCUAServer(),
      **{'security-policy': 'None', 'security-mode': 'None'})

  def test_new_topic_restarts_the_service(self):
    self.assertDataFlow()
    pid, = [p.pid for p in self.telegrafProcesses()]
    parameters = json.loads(self._instance_parameter_dict['_'])
    parameters['mqtt']['topic'] = 'plc/other'
    type(self)._instance_parameter_dict = {'_': json.dumps(parameters)}
    self.requestDefaultInstance()
    self.waitForInstance()
    self.assertEqual(self.config()['outputs']['mqtt'][0]['topic'], 'plc/other')
    self.assertDataFlow('plc/other')
    new_pid, = [p.pid for p in self.telegrafProcesses()]
    self.assertNotEqual(pid, new_pid)


@unittest.skipUnless(hasAsyncua(), 'asyncua is not available')
class TestOpcuaSecureDefaultClientCertificate(TelegrafTestCase):
  """The client uses the self-signed certificate that Telegraf creates."""

  @classmethod
  def getParameters(cls):
    directory = cls.makeTemporaryDirectory()
    server_certificate, server_key = makeCertificate(
      directory, 'server', 'urn:telegraf:test:server')
    return opcuaParameters(
      cls,
      endpoint=cls.startOPCUAServer(server_certificate, server_key),
      **{
        'security-policy': 'Basic256Sha256',
        'security-mode': 'SignAndEncrypt',
        'remote-certificate': readFile(server_certificate),
      })

  def test_values_reach_mqtt(self):
    self.assertDataFlow()

  def test_remote_certificate_is_a_private_file(self):
    opcua, = self.config()['inputs']['opcua']
    path = opcua['remote_certificate']
    self.assertTrue(path.startswith(str(self.computer_partition_root_path)))
    self.assertPrivateFile(path)

  def test_client_certificate_is_created_and_published(self):
    path = self.connectionParameters()['opcua-client-certificate']
    self.assertTrue(waitFor(lambda: os.path.exists(path)), path)


@unittest.skipUnless(hasAsyncua(), 'asyncua is not available')
class TestOpcuaSecureProvidedClientCertificate(TelegrafTestCase):
  """The client uses the certificate and the key given as parameters."""

  @classmethod
  def getParameters(cls):
    directory = cls.makeTemporaryDirectory()
    server_certificate, server_key = makeCertificate(
      directory, 'server', 'urn:telegraf:test:server')
    cls.client_certificate, cls.client_key = makeCertificate(
      directory, 'client', 'urn:telegraf:test:client')
    return opcuaParameters(
      cls,
      endpoint=cls.startOPCUAServer(server_certificate, server_key),
      **{
        'security-policy': 'Basic256Sha256',
        'security-mode': 'SignAndEncrypt',
        'certificate': readFile(cls.client_certificate),
        'private-key': readFile(cls.client_key),
        'remote-certificate': readFile(server_certificate),
      })

  def test_values_reach_mqtt(self):
    self.assertDataFlow()

  def test_files_are_written_as_given(self):
    opcua, = self.config()['inputs']['opcua']
    self.assertEqual(
      readFile(opcua['certificate']), readFile(self.client_certificate))
    self.assertEqual(
      readFile(opcua['private_key']), readFile(self.client_key))
    self.assertPrivateFile(opcua['private_key'])


class TestMqttTlsFiles(TelegrafTestCase):
  """The MQTT TLS files are written and referenced.

  The broker address is plain, so Telegraf starts without TLS. The test
  checks the files and the options of the configuration.
  """

  @classmethod
  def getParameters(cls):
    broker = cls.startBroker()
    directory = cls.makeTemporaryDirectory()
    cls.ca, _ = makeCertificate(directory, 'ca', 'urn:telegraf:test:ca')
    cls.certificate, cls.key = makeCertificate(
      directory, 'client', 'urn:telegraf:test:client')
    return {
      # Telegraf does not start without an input.
      'extra-config': '[[inputs.cpu]]\n',
      'mqtt': {
        'servers': ['mqtt://127.0.0.1:%s' % broker.port],
        'tls-ca': readFile(cls.ca),
        'tls-cert': readFile(cls.certificate),
        'tls-key': readFile(cls.key),
      },
    }

  def test_tls_files(self):
    mqtt, = self.config()['outputs']['mqtt']
    self.assertEqual(readFile(mqtt['tls_ca']), readFile(self.ca))
    self.assertEqual(readFile(mqtt['tls_cert']), readFile(self.certificate))
    self.assertEqual(readFile(mqtt['tls_key']), readFile(self.key))
    self.assertPrivateFile(mqtt['tls_key'])

  def test_service_runs(self):
    self.assertEqual(len(self.telegrafProcesses()), 1)


class TestInvalidParameters(TelegrafTestCase):
  """The instance fails when a certificate has no key."""

  @classmethod
  def getParameters(cls):
    return {'extra-config': '[[inputs.cpu]]\n'}

  def test_certificate_without_key_fails(self):
    type(self)._instance_parameter_dict = {'_': json.dumps({
      'opcua': {
        'endpoint': 'opc.tcp://127.0.0.1:1',
        'certificate': 'not a real certificate'}})}
    self.requestDefaultInstance()
    with self.assertRaises(SlapOSNodeCommandError):
      # a single attempt: the error does not go away on retry
      self.slap.waitForInstance(max_retry=0)
    # leave a valid instance for the cleanup
    type(self)._instance_parameter_dict = {'_': json.dumps(
      self.getParameters())}
    self.requestDefaultInstance()
    self.waitForInstance()
