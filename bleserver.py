import time
import argparse
from uuid import uuid4, UUID

from bluetooth.ble import BeaconService, GATTRequester


base_uuid = '5191-483F-B7B1-3D4745E634AD'
client_base_uuid = 'E19E-4D58-8FE4-73B60A0C6312'
client_base_uuid_bytes = UUID('00000000-' + client_base_uuid).bytes[4:]

def run_beacon(interface, beacon_uuid, major, minor, tx):
	service = BeaconService(interface)
	# discovery = DiscoveryService()

	if not beacon_uuid:
		beacon_uuid = str(uuid4())[:8]
		print 'Autogenerated UUID:', beacon_uuid

	if len(beacon_uuid) == 8:
		beacon_uuid += '-' + base_uuid

	def start_advertising():
		print 'Starting advertisement:'
		print ' ', beacon_uuid, '{}.{}'.format(major, minor), tx
		service.start_advertising(beacon_uuid, major, minor, tx, 200, 0x00e0, 0xbe, 0xac)
	start_advertising()
	try:
		while True:
			print 'service scan'
			# devices = discovery.discover(1)
			devices = service.scan(1)
			print 'devices:', len(devices)
			for address, data in devices.items():
				# print address, '.'.join('{:02x}'.format(x) for x in data)
				# print address, '.'.join('{:02x}'.format(x) for x in data[-1])
				# print '.'.join('{:02x}'.format(x) for x in data[-1][-16:])
				uuid = UUID(bytes=''.join(reversed([chr(x) for x in data[-1][-16:]])))
				print uuid, client_base_uuid
				if uuid.bytes[4:] == client_base_uuid_bytes:
					print 'found client:', uuid
					# service.stop_advertising()
					requester = GATTRequester(address, False)
					requester.connect(True)
					# connuuid = UUID(bytes=''.join(reversed(UUID('124BA72A-9F9E-4D58-96B8-19562AA06805').bytes)))
					# requester.read_by_uuid(str(connuuid))
					for i in range(3):
						print 'read by uuid'
						try:
							result = requester.read_by_uuid('124BA72A-9F9E-4D58-96B8-19562AA06805')
							# suuid = UUID(bytes=''.join(reversed(uuid.bytes)))
							# result = requester.read_by_uuid(str(suuid))
						except RuntimeError as e:
							print 'error:', e
						else:
							print 'result:', result
							break
					requester.disconnect()
					# start_advertising()
	except KeyboardInterrupt:
		print 'shutting down'
	service.stop_advertising()


def main():
	parser = argparse.ArgumentParser(description='BLE Test Server')
	parser.add_argument('--interface', '-i', default='hci0',
						help='bluetooth interface name')
	parser.add_argument('--uuid', '-u', default=None,
						help='advertisement UUID')
	parser.add_argument('--major', '-M', default=1, type=int,
						help='major version')
	parser.add_argument('--minor', '-m', default=1, type=int,
						help='minor version')
	parser.add_argument('--tx', '-t', default=-68, type=int, help='tx power')
	args = parser.parse_args()

	run_beacon(args.interface, args.uuid, args.major, args.minor, args.tx)


if __name__ == '__main__':
	main()
