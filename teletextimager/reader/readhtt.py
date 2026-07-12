#!/usr/bin/env python3

from teletextimager.reader import readt42

class TeletextReadHTT(readt42.TeletextReadT42):
	def read_packet(self, source):
		'''
		Reads 45 bytes from a file object, presumed to be an HTT file,
		and converts the HTT packet to a t42 packet.

		:param source: A file object.
		:returns: A bytearray of 42 bytes, or None if less than 45 bytes was read
		or if the first 3 bytes did not have a clock run-in and framing code.
		'''
		result = bytearray(source.read(45))

		if len(result) != 45:
			return None

		# Check for clock run-in and framing code
		if result[0:3] != b'\xaa\xaa\xe4':
			return None

		# Chop off the clock run-in and framing code
		# This leaves a t42 packet with the bits reversed
		result = result[3:]

		# Now reverse the bits
		for i in range(42):
			b = result[i]
			b = (b & 0xf0) >> 4 | (b & 0x0f) << 4
			b = (b & 0xcc) >> 2 | (b & 0x33) << 2
			b = (b & 0xaa) >> 1 | (b & 0x55) << 1
			result[i] = b

		return result
