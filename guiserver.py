from uuid import UUID, uuid4

import operator
from kivy import Logger
from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ObjectProperty
from kivy.clock import Clock, mainthread

from plyer import ble_central, ble_peripheral
from plyer.utils import iprop

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

	base_uuid = '5191-483F-B7B1-3D4745E634AD'
	client_base_uuid = 'E19E-4D58-8FE4-73B60A0C6312'
	client_base_uuid_bytes = UUID('00000000-' + client_base_uuid).bytes[4:]

	# beacon_uuid = UUID(str(uuid4())[:8] + '-' + base_uuid)
	beacon_uuid = UUID('1234abcd-' + base_uuid)

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

	def check_connect(self, *args):
		devices = list(sorted(ble_central.devices.values(), key=operator.attrgetter('age')))
		self.stop_scanning()
		self.ble_should_scan = False
		uuid_bytes = self.client_base_uuid_bytes
		for device in devices:
			if device.services:
				for uuid, service in device.services.items():
					if uuid.bytes[4:] == uuid_bytes:
						Logger.info('BLE: found device {}'.format(uuid))
						self.connect(device)
						return

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

	def on_device_disconnect(self, device, error=None):
		if error:
			Logger.error('BLE: device disconnected: {}'.format(error))
		else:
			Logger.info('BLE: device disconnected')
		self.connected = None
		self.ble_should_scan = True


if __name__ == '__main__':
	ModuleServerApp().run()
