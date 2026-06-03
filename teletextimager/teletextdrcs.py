#!/usr/bin/env python3

class TeletextDRCSDecode:
	def __init__(self):
		self.page = None

	def set_page(self, page):
		'''
		Sets the teletext page where the DRCS characters are defined.

		:param page: A list of teletext pages.
		'''
		self.page = page

	def ptu_mode(self, p, s=0):
		'''
		Returns the DRCS mode for a PTU as indicated by X/28/3.

		If X/28/3 is not present, 0 is returned.

		:param p: The PTU number. Must be between 0 and 47.
		:param s: The sub-table. Defaults to 0.
		:returns: An int, or None if the sub-table does not exist.
		'''
		if p > 47:
			return None

		if self.page == None:
			return None

		if s >= len(self.page):
			return None

		if not (28, 3) in self.page[s]:
			return 0

		pkt = self.page[s][(28, 3)]

		# Extract 4 bits from a packet of 13 triplets of 18 bits each
		t = p // 9 * 2 + 1
		m = p % 9

		if m < 4:
			return (pkt[t] >> (m * 4)) & 0xf
		elif m == 4:
			return ((pkt[t] >> 16) & 0x3) | ((pkt[t + 1] & 0x3) << 2)
		else: # elif m > 4
			return (pkt[t + 1] >> (m * 4 - 18)) & 0xf

	def ptu_l2p5(self, p, s=0, fp=0x01):
		'''
		Returns a bytearray of a Level 2.5 decoded DRCS character.

		The bytearray can be passed to ``Image.frombytes('P', (12, 10), data)``.

		:param p: The PTU number. Must be between 0 and 47.
		:param s: The sub-table. Defaults to 0.
		:param fp: Value of foreground pixels. Defaults to 0x01.
		:returns: A bytearray of 120 bytes, or None if no PTU was found.
		'''
		if self.page == None:
			return None

		if s >= len(self.page):
			return None

		y = (p + 2) // 2

		if not y in self.page[s]:
			return None

		start = p % 2 * 20

		# FIXME should we check all 20 D-bytes for SPACE instead of just the first D-byte?
		if self.page[s][y][start] < 0x40:
			return None

		result = bytearray()

		for i in range(start, start + 20):
			for b in range(6):
				if self.page[s][y][i] & (1 << (5 - b)):
					result.append(fp)
				else:
					result.append(0x00)

		return result

	def ptu_l3p5(self, p, s=0):
		'''
		Returns a bytearray of a Level 3.5 decoded DRCS character.

		For a DRCS mode 0, 1 or 2 character, the bytearray can be passed to
		``Image.frombytes('P', (12, 10), data)``. For a DRCS mode 3 character,
		the bytearray can be passed to ``Image.frombytes('P', (6, 5), data)``.

		:param p: The PTU number. Must be between 0 and 47.
		:param s: The sub-table. Defaults to 0.
		:returns: For a DRCS mode 0, 1 or 2 character, a bytearray of 120 bytes. For
			a DRCS mode 3 character, a bytearray of 30 bytes. Or None if no PTU was
			found.
		'''
		mode = self.ptu_mode(p, s)

		if mode == None:
			# X/28/3 not present, assume mode 0
			mode = 0
		elif mode == 3:
			# Some duplicate code from ptu_l2p5
			if self.page == None:
				return None

			if s >= len(self.page):
				return None

			y = (p + 2) // 2

			if not y in self.page[s]:
				return None

			start = p % 2 * 20

			# FIXME should we check all 20 D-bytes for SPACE instead of just the first D-byte?
			if self.page[s][y][start] < 0x40:
				return None

			# Mode 3 - 6x5 pixels with 4 bitplanes
			# First row of six pixels is stored four times sequentially, one for
			# each bitplane, then second row of pixels four times, and so on
			result = bytearray()

			for r in range(5):
				row_bytes = bytearray(6)
				for bp in range(4):
					for c in range(6):
						if self.page[s][y][start + r * 4 + bp] & (1 << (5 - c)):
							row_bytes[c] |= 1 << bp
				result += row_bytes

			return result

		# Mode 0, 1 or 2 character - 12x10 pixels with 1, 2 or 4 bitplanes
		# Each complete bitplane stored sequentially across multiple PTUs

		# This will be a complete mode 0 character, or the first bitplane
		# of a mode 1 or 2 character
		result = self.ptu_l2p5(p, s)

		if mode == 1 or mode == 2:
			# Get second bitplane of mode 1 or 2 character and OR the bitplanes together
			bp2 = self.ptu_l2p5(p + 1, s, 0x02)
			if bp2 != None:
				result = bytearray(ab | bb for ab, bb in zip(result, bp2))

			if mode == 2:
				# Get third and fourth bitplanes of mode 2 character and OR the bitplanes together
				bp3 = self.ptu_l2p5(p + 2, s, 0x04)
				if bp3 != None:
					result = bytearray(ab | bb for ab, bb in zip(result, bp3))

				bp4 = self.ptu_l2p5(p + 3, s, 0x08)
				if bp4 != None:
					result = bytearray(ab | bb for ab, bb in zip(result, bp4))

		return result
