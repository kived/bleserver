from time import sleep

# import os
# os.environ['PYOBJUS_DEBUG'] = '1'

import random
from uuid import UUID, uuid4

import operator
from kivy import Logger
from kivy.app import App
from kivy.config import Config
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ObjectProperty
from kivy.clock import Clock, mainthread
from struct import pack

from plyer import ble_central, ble_peripheral
from plyer.utils import iprop

Config.set('kivy', 'log_level', 'debug')

root = lambda: Builder.load_string('''
BoxLayout:
	orientation: 'vertical'

	Label:
		size_hint_y: None
		font_size: sp(24)
		text_size: self.width, None
		height: self.texture_size[1] + dp(12)
		text: 'SmartModule Demo: {}'.format(app.beacon_uuid)
	Button:
		text: 'Cancel Handshake'
		disabled: not app.connecting
		on_release: app.disconnect()
''')

class ModuleServerApp(App):
	ble_central_ready = BooleanProperty(False)
	ble_peripheral_ready = BooleanProperty(False)

	ble_scanning = BooleanProperty(False)
	ble_should_scan = BooleanProperty(False)
	ble_advertising = BooleanProperty(False)

	connecting = ObjectProperty(allownone=True)
	connected = ObjectProperty(allownone=True)
	connect_uuid = ObjectProperty(allownone=True)

	streaming_data = BooleanProperty(False)

	base_uuid = '5191-483F-B7B1-3D4745E634AD'
	client_base_uuid = 'E19E-4D58-8FE4-73B60A0C6312'
	client_base_uuid_bytes = UUID('00000000-' + client_base_uuid).bytes[4:]

	# beacon_uuid = UUID(str(uuid4())[:8] + '-' + base_uuid)
	beacon_uuid = UUID('1234abcd-' + base_uuid)

	# characteristic uuids
	connection_uuid = UUID('124BA72A-9F9E-4D58-96B8-19562AA06805')
	module_message_uuid = UUID('81DFAD82-C635-43E3-89A9-C496DE48D70F')
	client_message_uuid = UUID('20C336BD-FC96-4AA6-A601-8998463E2B2A')
	module_data_uuid = UUID('1D6C9B50-7FB7-4AF9-8C6E-377441E19251')
	client_data_uuid = UUID('FA3E71D3-A8A4-4B77-99BF-DCE23E9E29B9')

	def build(self):
		return root()

	def on_start(self):
		ble_central.init()
		# ble_central.set_callbacks(on_state=self.central_state_changed)
		ble_central.set_callbacks(on_state=self.central_state_changed,
		                          on_discover=self.central_discovered_peripheral)
		ble_peripheral.init()
		ble_peripheral.set_callbacks(on_state=self.peripheral_state_changed,
		                             on_service_added=self.peripheral_service_added,
		                             on_service_error=self.peripheral_service_error,
		                             on_advertising_started=self.peripheral_advertising_started,
		                             on_advertising_error=self.peripheral_advertising_error)

	def on_stop(self):
		if self.ble_advertising:
			self.stop_advertising()
		self.disconnect()

	def central_state_changed(self, state):
		Logger.debug('BLE: central state changed: {}'.format(state))
		self.ble_central_ready = ble_central.has_ble

	def peripheral_state_changed(self, state):
		Logger.debug('BLE: peripheral state changed: {}'.format(state))
		self.ble_peripheral_ready = ble_peripheral.has_ble

	def peripheral_service_added(self, service):
		Logger.debug('BLE: connect: peripheral service added: {}'.format(service))

	def peripheral_service_error(self, service, error):
		Logger.error('BLE: connect: peripheral service error: {}: {}'.format(service, error))

	def peripheral_advertising_started(self):
		Logger.debug('BLE: connect: advertisement started')

	def peripheral_advertising_error(self, error):
		Logger.error('BLE: connect: advertisement error: {}'.format(error))

	def on_ble_peripheral_ready(self, obj, ready):
		if ready:
			if not self.ble_advertising:
				self.start_advertising()
		elif self.ble_advertising:
			self.stop_advertising()

	def on_ble_central_ready(self, obj, ready):
		self.check_scanning()

	def on_ble_should_scan(self, obj, scan):
		self.check_scanning()

	def start_advertising(self):
		Logger.info('BLE: start advertising')
		service = ble_peripheral.Service(self.beacon_uuid)
		# char = ble_peripheral.Characteristic(uuid4(),
		#     value=b'1', permissions=ble_peripheral.Characteristic.permission.readable,
		#     properties=ble_peripheral.Characteristic.property.read)
		ble_peripheral.add_service(service)
		ble_peripheral.start_advertising('SmartModule Demo')
		self.ble_advertising = True
		self.ble_should_scan = True

	def stop_advertising(self):
		Logger.info('BLE: stop advertising')
		ble_peripheral.stop_advertising()
		self.ble_advertising = False
		self.ble_should_scan = False

	def check_scanning(self):
		if self.ble_central_ready and self.ble_should_scan:
			if not self.ble_scanning:
				self.start_scanning()
		elif self.ble_scanning:
			self.stop_scanning()

	def start_scanning(self):
		Logger.info('BLE: start scanning')
		ble_central.start_scanning(allow_duplicates=False)
		# Clock.schedule_once(self.check_connect, 5)
		# Clock.schedule_interval(self.check_connect, 0.5)

	def stop_scanning(self):
		Logger.info('BLE: stop scanning')
		ble_central.stop_scanning()
		# Clock.unschedule(self.check_connect)

	# def check_connect(self, *args):
	# 	devices = list(sorted(ble_central.devices.values(), key=operator.attrgetter('age')))
	# 	self.stop_scanning()
	# 	self.ble_should_scan = False
	# 	uuid_bytes = self.client_base_uuid_bytes
	# 	for device in devices:
	# 		if device.services:
	# 			for uuid, service in device.services.items():
	# 				if uuid.bytes[4:] == uuid_bytes:
	# 					Logger.info('BLE: found device {}'.format(uuid))
	# 					self.connect(device)
	# 					return

	# @mainthread
	def central_discovered_peripheral(self, device):
		if self.connecting or self.connected:
			return
		print('discovered peripheral, state', iprop(device.peripheral.state))
		uuid_bytes = self.client_base_uuid_bytes
		for uuid, service in device.services.items():
			if uuid.bytes[4:] == uuid_bytes:
				Logger.info('BLE: found device {}'.format(uuid))
				self.ble_should_scan = False
				self.stop_scanning()
				self.connect_uuid = uuid
				self.connect(device)
				return

	# @mainthread
	def connect(self, device):
		Logger.info('BLE: connecting to device {}'.format(device))
		# self.ble_should_scan = False
		# self.stop_scanning()
		self.connecting = device
		device.connect(self.on_device_connect, self.on_device_disconnect)

	def disconnect(self):
		if self.connecting:
			print('connecting state', iprop(self.connecting.peripheral.state))
			self.connecting.disconnect()
		if self.connected:
			self.connected.disconnect()

	def on_device_connect(self, device, error=None):
		self.connecting = None
		if error:
			Logger.error('BLE: failed to connect to device: {}'.format(error))
			self.ble_should_scan = True
			return

		Logger.info('BLE: connected to device {}'.format(device))
		self.connected = device

		# device.discover_services(uuids=(self.connect_uuid,), on_discover=self.on_discover_services)
		service = device.services[self.connect_uuid]
		if service:
			Logger.info('BLE: found service {}'.format(service))
			self.on_discover_services(device.services, None)
		else:
			device.discover_services(on_discover=self.on_discover_services)

	def on_device_disconnect(self, device, error=None):
		if error:
			Logger.error('BLE: device disconnected: {}'.format(error))
		else:
			Logger.info('BLE: device disconnected')
		self.connected = None
		self.ble_should_scan = True

	def on_discover_services(self, services, error):
		if error:
			Logger.error('BLE: error discovering services: {}'.format(error))
			return

		Logger.info('BLE: discovered services: {}'.format(services.keys()))

		service = services[self.connect_uuid]
		if not service:
			Logger.error('BLE: service not found!')
			return

		service.discover_characteristics(on_discover=self.on_discover_characteristics)

	def on_discover_characteristics(self, characteristics, error):
		if error:
			Logger.error('BLE: error discovering characteristics: {}'.format(error))
			return

		# Logger.info('BLE: discovered characteristics: {}'.format(characteristics.keys()))
		for uuid, char in characteristics.items():
			Logger.info('BLE: discovered characteristic: {} {:02x}'.format(uuid, char.properties))
			if uuid == self.connection_uuid:
				Logger.info('BLE: found connection characteristic')
				char.read(on_read=self.on_connection_established)
			elif uuid == self.module_message_uuid:
				Logger.info('BLE: found module message characteristic')
				self.module_message_characteristic = char

	def on_connection_established(self, characteristic, error):
		if error:
			Logger.error('BLE: connection failed: {}'.format(error))
			self.on_device_disconnect(None)
			return
		Logger.info('BLE: connection established {}'.format(repr(characteristic.value)))
		self.start_data()

	def start_data(self):
		if not self.streaming_data:
			self.streaming_data = True
			self.T1_data = 66
			self.T2_data = 72
			self.T3_data = 66
			self.T4_data = 68
			self.humid_data = 40
			self.barom_data = 15
			self.accelx_data = 0.
			self.accely_data = 0.
			self.accelz_data = 0.
			self.impact_data = 0.
			self.max_impact_data = 0.

			Clock.schedule_interval(self.stream_data, 0.5)
			self.stream_data()

	def stop_data(self):
		if self.streaming_data:
			self.streaming_data = False
			Clock.unschedule(self.stream_data)

	def update_value(self, name, fn):
		data = getattr(self, name + '_data')
		setattr(self, name + '_data', fn(data))

	def vary_value(self, name, magnitude, distribution=5):
		bell = sum(random.random() for i in range(distribution)) / float(distribution)
		variance = bell * 2. - 1.
		variance *= magnitude
		self.update_value(name, lambda x: x + variance)

	def set_value(self, name, max_value, distribution=5):
		bell = sum(random.random() for i in range(distribution)) / float(distribution)
		value = bell * 2. - 1.
		value *= max_value
		self.update_value(name, lambda x: value)

	def stream_data(self, *args):
		self.vary_value('T1', 0.5)
		self.vary_value('T2', 1.)
		self.vary_value('T3', 0.5)
		self.vary_value('T4', 0.5)
		self.vary_value('humid', 0.5)
		self.vary_value('barom', 0.1)
		self.vary_value('accelx', 0.01)
		self.vary_value('accely', 0.01)
		self.vary_value('accelz', 0.01)
		self.set_value('impact', 20, distribution=10)
		self.impact_data = abs(self.impact_data)
		self.max_impact_data = max(self.impact_data, self.max_impact_data)

		char = self.module_message_characteristic
		# char.write(pack('Bffff', 1, self.T1_data, self.T2_data, self.T3_data, self.T4_data), self.on_char_write)
		char.write(chr(1) + pack('ffff', self.T1_data, self.T2_data, self.T3_data, self.T4_data), self.on_char_write)
		char.write(chr(2) + pack('f', self.humid_data), self.on_char_write)
		char.write(chr(3) + pack('f', self.barom_data), self.on_char_write)
		char.write(chr(4) + pack('fff', self.accelx_data, self.accely_data, self.accelz_data), self.on_char_write)
		char.write(chr(5) + pack('ff', self.impact_data, self.max_impact_data), self.on_char_write)

	def on_char_write(self, char, error):
		if error:
			Logger.error('BLE: error writing data: {}: {}'.format(char, error))
		else:
			Logger.debug('BLE: write successful: {}'.format(char))

if __name__ == '__main__':
	ModuleServerApp().run()
