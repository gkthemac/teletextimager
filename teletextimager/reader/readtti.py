#!/usr/bin/env python3

class TeletextReadTTI:
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

			if cur_line.startswith('OL,'):
				if cur_line[4] == ",":
					pkt_no = ord(cur_line[3]) - 48
					line_start = 5
				else:
					pkt_no = (ord(cur_line[3]) - 48) * 10 + ord(cur_line[4]) - 48
					line_start = 6
				if pkt_no >= 0 and pkt_no <= 25:
					pkt = bytearray(40)
					i = line_start
					for j in range(40):
						if i >= len(cur_line):
							break
						this_char = ord(cur_line[i])
						if this_char == 0x10:
							this_char = 0x0d
						elif this_char == 0x1b:
							i += 1
							this_char = ord(cur_line[i]) - 0x40
						pkt[j] = this_char
						i += 1
					cur_page[pkt_no] = bytes(pkt)
				elif pkt_no >= 26 and pkt_no <= 28:
					triplets = []
					desig_no = ord(cur_line[line_start]) - 64
					for t in range(line_start + 1, line_start + 39, 3):
						triplet1 = ord(cur_line[t]) & 0x3f
						triplet2 = ord(cur_line[t+1]) & 0x3f
						triplet3 = ord(cur_line[t+2]) & 0x3f
						triplet = (triplet3 << 12) | (triplet2 << 6) | triplet1
						triplets.append(triplet)
					cur_page[(pkt_no, desig_no)] = triplets

		if source_is_file:
			source.close()

		return pages
