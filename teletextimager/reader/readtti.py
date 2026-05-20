#!/usr/bin/env python3

class TeletextReadTTI:
	def convert_7bit_packet(self, line_pkt):
		'''
		Convert a 7-bit OL line into an array of 40 bytes
		'''
		result = bytearray(40)
		i = 0

		for j in range(40):
			if i >= len(line_pkt):
				break
			this_char = ord(line_pkt[i])
			if (this_char & 0x80) == 0x80:
				this_char &= 0x7f
			elif this_char == 0x10:
				this_char = 0x0d
			elif this_char == 0x1b:
				i += 1
				this_char = ord(line_pkt[i]) & 0x1f
			result[j] = this_char
			i += 1

		return result

	def convert_18bit_packet(self, line_pkt):
		'''
		Convert an 18-bit OL line into a list of 13 triplets
		'''
		result = []

		for t in range(1, 39, 3):
			triplet1 = ord(line_pkt[t]) & 0x3f
			triplet2 = ord(line_pkt[t+1]) & 0x3f
			triplet3 = ord(line_pkt[t+2]) & 0x3f
			triplet = (triplet3 << 12) | (triplet2 << 6) | triplet1
			result.append(triplet)

		return result

	def convert_4bit_packet(self, line_pkt):
		'''
		Convert a 4-bit OL line into an array of 40 bytes
		'''
		result = bytearray(40)

		for i in range(40):
			if i >= len(line_pkt):
				break
			result[i] = ord(line_pkt[i]) & 0x0f

		return result

	def read(self, source):
		source_is_file = False
		if not hasattr(source, 'read'):
			source = open(source)
			source_is_file = True

		pages = [ ]
		# Pre-create the first page in case a PS command comes before the first PN
		pages.append( { } )
		cur_page = pages[-1]
		cur_page['control_bits'] = set()
		first_pn = False

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
					cur_page['control_bits'] = pages[-2]['control_bits'].copy()
				ps_value = cur_line.rpartition(',')[-1]
				cur_page['number'] = int(ps_value[:3], 16)
				cur_page['subcode'] = int(ps_value[3:], 16)

			if cur_line.startswith('SC,'):
				cur_page['subcode'] = int(cur_line.rpartition(',')[-1], 16)

			if cur_line.startswith('PS,'):
				status_bits = int(cur_line.rpartition(',')[-1], 16)
				# Create an empty set
				cur_page['control_bits'].clear()
				# Get bits C5 to C11
				for b in range(0, 7):
					t = 1 << b
					if (status_bits & t) == t:
						cur_page['control_bits'].add(b + 5)
				# Get bit C4
				if (status_bits & 0x4000) == 0x4000:
					cur_page['control_bits'].add(4)
				# Get bits C12-C14 as they seem to be stored backwards in TTI
				if (status_bits & 0x200) == 0x200:
					cur_page['control_bits'].add(12)
				if (status_bits & 0x100) == 0x100:
					cur_page['control_bits'].add(13)
				if (status_bits & 0x80) == 0x80:
					cur_page['control_bits'].add(14)

			if cur_line.startswith('RE,'):
				cur_page['region'] = int(cur_line[3], 16)

			if cur_line.startswith('OL,'):
				# Fiddly way of extracting the line number as an integer
				if cur_line[4] == ',':
					pkt_no = ord(cur_line[3]) - 48
					line_pkt = cur_line[5:]
				else:
					pkt_no = (ord(cur_line[3]) - 48) * 10 + ord(cur_line[4]) - 48
					line_pkt = cur_line[6:]

				desig_no = None

				if pkt_no >= 26 and pkt_no <= 29:
					desig_no = ord(line_pkt[0]) & 0xf
					if pkt_no == 27 and desig_no < 4:
						convert_packet = self.convert_4bit_packet
					else:
						convert_packet = self.convert_18bit_packet
				elif pkt_no >= 0 and pkt_no <= 25:
					# TODO deal with packet encodings
					convert_packet = self.convert_7bit_packet

				if desig_no == None:
					cur_page[pkt_no] = convert_packet(line_pkt)
				else:
					cur_page[(pkt_no, desig_no)] = convert_packet(line_pkt)

			if cur_line.startswith('FL,'):
				links = cur_line.split(',')
				if len(links) == 7:
					# Init packet to mostly 0xf's as page xFF:3F7F means no page is specified
					fl_packet = bytearray([0xf] * 40)
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
