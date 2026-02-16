#!/usr/bin/env python3

import copy

from teletextimager import hamming_8_4, hamming_24_18

class TeletextReadT42:
	def __init__(self):
		# Eight pages, one for each magazine
		self.page = [{} for _ in range(8)]
		# Used for tracking consecutive X/0's with same page number
		self.pkt_0_page_no = [None] * 8

	def read(self, source):
		# We can take either a filename or a Python file object
		source_is_file = False
		if not hasattr(source, 'read'):
			source = open(source, 'rb')
			source_is_file = True

		read_something = False

		mag_no = None

		while True:
			t42_packet = bytearray(source.read(42))
			if len(t42_packet) != 42:
				if mag_no != None:
					result_page = self.page[mag_no]
				break

			read_something = True

			# Magazine and packet number
			t42_packet[0] = hamming_8_4.decode(t42_packet[0])
			t42_packet[1] = hamming_8_4.decode(t42_packet[1])
			if t42_packet[0] == 0xff or t42_packet[1] == 0xff:
				# Error decoding magazine or packet number
				continue

			mag_no = t42_packet[0] & 0x07
			pkt_no = (t42_packet[0] >> 3) | (t42_packet[1] << 1)

			cur_page = self.page[mag_no]

			if pkt_no == 0:
				# Hamming decode page number, subcodes and control bits
				for b in range(2, 10):
					t42_packet[b] = hamming_8_4.decode(t42_packet[b])
					# Neutralise decoding-failed bits to zero apart from page number
					if t42_packet[b] == 0xff and b > 3:
						t42_packet[b] = 0x00

				# See if the page number decoded
				if t42_packet[2] == 0xff or t42_packet[3] == 0xff:
					# Error decoding page number
					continue

				page_no = (t42_packet[3] << 4) | t42_packet[2]

				if page_no == 0xff:
					# Time filling header
					continue

				if page_no == self.pkt_0_page_no[mag_no]:
					# Consecutive X/0's with same page number
					continue
				# Take a note of page number in case of consecutive X/0's
				self.pkt_0_page_no[mag_no] = page_no

				first_page_in_mag = not self.page[mag_no]

				if not first_page_in_mag:
					# A full page has been previously stored before this X/0
					# Take a copy of this page to return later; we're about to wipe it
					# so we can store the page address and control bits of the upcoming page
					result_page = copy.deepcopy(self.page[mag_no])

				self.page[mag_no].clear()

				cur_page = self.page[mag_no]

				cur_page['control_bits'] = set()

				cur_page['number'] = (mag_no << 8) | page_no
				if mag_no == 0:
					cur_page['number'] |= 0x800

				cur_page['subcode'] = ((t42_packet[7] & 0x3) << 12) | (t42_packet[6] << 8) | ((t42_packet[5] & 0x7) << 4) | t42_packet[4]

				# Get bits C4-C6
				if (t42_packet[5] & 0x08) == 0x08:
					cur_page['control_bits'].add(4)
				if (t42_packet[7] & 0x04) == 0x04:
					cur_page['control_bits'].add(5)
				if (t42_packet[7] & 0x08) == 0x08:
					cur_page['control_bits'].add(6)
				# Get bits C7-C10
				for b in range(0, 4):
					t = 1 << b
					if (t42_packet[8] & t) == t:
						cur_page['control_bits'].add(b + 7)
				# Get bits C11-C14
				if (t42_packet[9] & 0x01) == 0x01:
					cur_page['control_bits'].add(11)
				if (t42_packet[9] & 0x08) == 0x08:
					cur_page['control_bits'].add(12)
				if (t42_packet[9] & 0x04) == 0x04:
					cur_page['control_bits'].add(13)
				if (t42_packet[9] & 0x02) == 0x02:
					cur_page['control_bits'].add(14)

				# "Unparity" the text in the header row
				for b in range(10, 42):
					t42_packet[b] &= 0x7f

				cur_page[0] = b'        ' + t42_packet[10:]

				if not first_page_in_mag:
					break

				continue

			# Disregard whole magazine packets for now
			if pkt_no > 28:
				continue

			# This will "continue" if X/0 didn't occur before this packet
			if not self.page[mag_no]:
				continue

			# Not a consecutive X/0 now
			self.pkt_0_page_no[mag_no] = None

			if pkt_no < 26:
				# X/1-25, assumes page is 7-bit odd parity coded!
				for b in range(2, 42):
					t42_packet[b] &= 0x7f

				cur_page[pkt_no] = t42_packet[2:]
				continue

			# X/26, X/27 or X/28
			desig_no = hamming_8_4.decode(t42_packet[2])

			if desig_no == 0xff:
				# Error decoding designation code
				continue

			# X/27/0-3 is hamming 8/4 encoded
			# We're just displaying a page so we don't need FLOF links
			if pkt_no == 27 and desig_no < 4:
				continue

			# Packet is 13 hamming 24/18 encoded triplets
			triplets = []

			for t in range(3, 41, 3):
				p0 = t42_packet[t]
				p1 = t42_packet[t + 1]
				p2 = t42_packet[t + 2]

				d = hamming_24_18.decode(p0, p1, p2)

				if (d & 0x80000000) == 0x80000000:
					triplets.append(None)
				else:
					triplets.append(d)

			cur_page[(pkt_no, desig_no)] = triplets

		if source_is_file:
			source.close()

		if not read_something:
			return None

		# Return page within a single entry list
		pages = []
		pages.append(result_page)

		return pages
