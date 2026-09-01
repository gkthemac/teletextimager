#!/usr/bin/env python3

from enum import IntEnum

class TeletextReadTTI:
	class PFSource(IntEnum):
		'''
		TTI has an explicit PF command which stores the page function
		and coding, but TTI can also carry an X/28 packet which also stores
		that info.

		We try to copy vbit2's behaviour in that if both are found, the
		coding specified in X/28 has priority over a PF command.
		'''
		# Neither a PF command or X/28 was found yet
		PF_NONE = 0
		# PF command found
		PF_COMMAND = 1
		# Coding found within X/28/0 packet
		PF_X28 = 2

	def convert_7bit_packet(self, pkt):
		'''
		Convert a 7-bit OL line into an array of 40 bytes.

		:param pkt: A string of 40 characters.
		:returns: A bytearray of 40 bytes.
		'''
		result = bytearray([0x20] * 40)
		i = 0

		for j in range(40):
			if i >= len(pkt):
				break
			this_char = ord(pkt[i])
			if (this_char & 0x80) == 0x80:
				this_char &= 0x7f
			elif this_char == 0x10:
				this_char = 0x0d
			elif this_char == 0x1b:
				i += 1
				this_char = ord(pkt[i]) & 0x1f
			result[j] = this_char
			i += 1

		return result

	def convert_18bit_packet(self, pkt):
		'''
		Convert an 18-bit OL line into a list of 13 triplets.

		:param pkt: A string of 40 characters.
		:returns: A list of 13 integers, one for each triplet.
		'''
		result = []

		for t in range(1, 39, 3):
			triplet1 = ord(pkt[t]) & 0x3f
			triplet2 = ord(pkt[t+1]) & 0x3f
			triplet3 = ord(pkt[t+2]) & 0x3f
			triplet = (triplet3 << 12) | (triplet2 << 6) | triplet1
			result.append(triplet)

		return result

	def convert_18bit_packet_nibble(self, pkt):
		'''
		Convert an 18-bit OL line into a list of 13 triplets and one nibble.

		:param pkt: A string of 40 characters.
		:returns: A list of 14 integers.
			The first 13 entries are for each triplet and the last entry is for
			the nibble at the start of the packet.
		'''
		result = self.convert_18bit_packet(pkt)
		result.append(ord(pkt[0]) & 0xf)

		return result

	def convert_4bit_packet(self, pkt):
		'''
		Convert a 4-bit OL line into a list of 40 nibbles.

		:param pkt: A string of 40 characters.
		:returns: A list of 40 integers, one for each nibble.
		'''
		result = [0] * 40

		for i in range(40):
			if i >= len(pkt):
				break
			result[i] = ord(pkt[i]) & 0x0f

		return result

	def converter_from_coding(self, coding):
		'''
		Returns function for packet converter based on coding
		'''
		if coding == 2:
			return self.convert_18bit_packet_nibble
		elif coding == 3:
			return self.convert_4bit_packet
		# elif coding == 0:
		return self.convert_7bit_packet

	def read(self, source):
		source_is_file = False
		if not hasattr(source, 'read'):
			source = open(source)
			source_is_file = True

		pages = [ ]
		# Pre-create the first page in case a PS command comes before the first PN
		pages.append( { } )
		cur_page = pages[-1]
		cur_page['control'] = set()

		first_pn = False

		pf_source = self.PFSource.PF_NONE
		page_coding = 0
		# Reference to function that converts X/1-X/25
		convert_body_packet = self.convert_7bit_packet

		for cur_line in source:
			if cur_line.startswith('DE,'):
				cur_page.setdefault('metadata', {})
				cur_page['metadata']['title'] = cur_line.partition(',')[2].rstrip()

			if cur_line.startswith('PN,'):
				if not first_pn:
					first_pn = True
				else:
					pages.append( { } )
					cur_page = pages[-1]
					# Copy status bits from previous page in case only the first
					# page has a PS command
					cur_page['control'] = pages[-2]['control'].copy()
				ps_value = cur_line.rpartition(',')[-1]
				cur_page['number'] = int(ps_value[:3], 16)
				cur_page['subcode'] = int(ps_value[3:], 16)

			if cur_line.startswith('SC,'):
				cur_page['subcode'] = int(cur_line.rpartition(',')[-1], 16)

			if cur_line.startswith('PS,'):
				status_bits = int(cur_line.rpartition(',')[-1], 16)
				# Create an empty set
				cur_page['control'].clear()
				# Get bits C5 to C11
				for b in range(0, 7):
					t = 1 << b
					if (status_bits & t) == t:
						cur_page['control'].add(b + 5)
				# Get bit C4
				if (status_bits & 0x4000) == 0x4000:
					cur_page['control'].add(4)
				# Get bits C12-C14 as they seem to be stored backwards in TTI
				if (status_bits & 0x200) == 0x200:
					cur_page['control'].add(12)
				if (status_bits & 0x100) == 0x100:
					cur_page['control'].add(13)
				if (status_bits & 0x80) == 0x80:
					cur_page['control'].add(14)

			if cur_line.startswith('RE,'):
				cur_page['region'] = int(cur_line[3], 16)

			if cur_line.startswith('PF,'):
				pf_params = cur_line.split(',')
				if len(pf_params) == 3 and pf_source < self.PFSource.PF_X28:
					pf_source = self.PFSource.PF_COMMAND

					# page_function = int(pf_params[1])
					page_coding = int(pf_params[2])

					convert_body_packet = self.converter_from_coding(page_coding)

			if cur_line.startswith('OL,'):
				# Fiddly way of extracting the line number as an integer
				if cur_line[4] == ',':
					pkt_no = ord(cur_line[3]) - 48
					line_pkt = cur_line[5:].rstrip('\r\n')
				else:
					pkt_no = (ord(cur_line[3]) - 48) * 10 + ord(cur_line[4]) - 48
					line_pkt = cur_line[6:].rstrip('\r\n')

				desig_no = None

				if pkt_no == 0:
					convert_packet = self.convert_7bit_packet
				elif pkt_no >= 1 and pkt_no <= 25:
					convert_packet = convert_body_packet
				elif pkt_no >= 26 and pkt_no <= 29:
					desig_no = ord(line_pkt[0]) & 0xf
					if pkt_no == 27 and desig_no < 4:
						convert_packet = self.convert_4bit_packet
					else:
						convert_packet = self.convert_18bit_packet

				if desig_no == None:
					cur_page[pkt_no] = convert_packet(line_pkt)
				else:
					cur_page[(pkt_no, desig_no)] = convert_packet(line_pkt)

				if pkt_no == 28 and desig_no <= 4 and desig_no != 1 and pf_source != self.PFSource.PF_X28:
					pf_source = self.PFSource.PF_X28

					# page_function = cur_page[(28, desig_no)][0] & 0x0f
					page_coding = (cur_page[(28, desig_no)][0] >> 4) & 0x07

					convert_body_packet = self.converter_from_coding(page_coding)

			if cur_line.startswith('FL,'):
				links = cur_line.split(',')
				if len(links) == 7:
					# Init packet to mostly 0xf's as page xFF:3F7F means no page is specified
					fl_packet = [0xf] * 40

					fl_packet[0] = 0x0  # Designation code
					fl_packet[38] = 0x0 # CRC word
					fl_packet[39] = 0x0 # CRC word

					# Page numbers in FL command reference absolute magazine number
					# Convert to relative by XORing with page magazine number
					if 'number' in cur_page:
						mag_flip = cur_page['number'] & 0x700
					else:
						mag_flip = 0

					for i in range(6):
						link_rel = (int(links[i+1], 16) & 0x7ff) ^ mag_flip
						fl_packet[i*6+1] = link_rel & 0x00f
						fl_packet[i*6+2] = (link_rel & 0x0f0) >> 4
						fl_packet[i*6+4] = 0x7 | ((link_rel & 0x100) >> 5)
						fl_packet[i*6+6] = 0x3 | ((link_rel & 0x600) >> 7)

					cur_page[(27, 0)] = fl_packet

			if cur_line.startswith('CT,'):
				cycle = cur_line.split(',')
				if len(cycle) == 3 and cycle[1].isdigit():
					cycle_type = cycle[2].rstrip()
					if cycle_type == 'C':
						cur_page.setdefault('metadata', {})
						cur_page['metadata']['cycle_cycles'] = int(cycle[1])
					elif cycle_type == 'T':
						cur_page.setdefault('metadata', {})
						cur_page['metadata']['cycle_seconds'] = int(cycle[1])

		if source_is_file:
			source.close()

		return pages
