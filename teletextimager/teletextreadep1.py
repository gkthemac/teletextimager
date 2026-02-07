#!/usr/bin/env python3

class TeletextReadEP1:
	# Language codes unique to EP1
	# EP1 code: (region, NOS bits)
	language_map = {
		0x07: (0, 6),  # Czech/Slovak
		0x08: (0, 2),  # Danish? Actually Swedish/Finnish
		0x09: (0, 0),  # English
		0x0b: (0, 4),  # French
		0x0d: (0, 1),  # German
		0x0e: (6, 7),  # Greek
		0x11: (0, 3),  # Italian
		0x14: (1, 0),  # Polish
		0x16: (3, 7),  # Rumanian
		0x17: (0, 5),  # Portuguese/Spanish
		0x18: (0, 2),  # Swedish/Finnish
		0x1c: (2, 6),  # Turkish
		0x1e: (3, 5),  # Serbian/Croatian/Slovenian
		0xff: (4, 3)   # Lettish/Lithuanian - but could be Estonian or and Hungarian
	}

	def read(self, source):
		# We can take either a filename or a Python file object
		source_is_file = False
		if not hasattr(source, 'read'):
			source = open(source, 'rb')
			source_is_file = True

		pages = []
		# Create the first subpage and point to it
		pages.append({})
		cur_page = pages[-1]
		cur_page['control_bits'] = set()

		num_pages_left = 1
		subcode = 0

		while num_pages_left != 0:
			# Read six bytes, will either be a header for a (sub)page
			# or a start header indicating multiple subpages are within
			preamble = source.read(6)
			if len(preamble) != 6:
				break

			if preamble[0:3] == b'JWC':
				# Multiple subpages: get number of subpages
				num_pages_left = preamble[3]
				subcode = 1
				# then read next six bytes that really will be the header of the first subpage
				preamble = source.read(6)
				if len(preamble) != 6:
					break

			# Check for header of a subpage
			if preamble[0:2] != b'\xfe\x01':
				break

			# Deal with language code unique to EP1 - unknown values are mapped to English
			region, nos = self.language_map.get(preamble[2], (0, 0))

			cur_page['region'] = region

			if (nos & 0x1) == 0x1:
				cur_page['control_bits'].add(12)
			if (nos & 0x2) == 0x2:
				cur_page['control_bits'].add(13)
			if (nos & 0x4) == 0x4:
				cur_page['control_bits'].add(14)

			# If fourth byte is 0xca then "X/26 enhancements header" follows
			# Otherwise Level 1 page data follows
			if preamble[3] == 0xca:
				# Read next four bytes that form the "X/26 enhancements header"
				x26_preamble = source.read(4)
				if len(x26_preamble) != 4:
					break
				# Third and fourth bytes are little-endian length of enhancement data
				num_x26_bytes = x26_preamble[2] | (x26_preamble[3] << 8)
				num_x26_packets = (num_x26_bytes + 39) // 40

				for d in range(0, num_x26_packets):
					triplets = []

					packet_read = source.read(40)
					if len(packet_read) != 40:
						break

					# Assumes that X/26 packets are saved with ascending designation codes...
					for b in range(1, 39, 3):
						t_address = packet_read[b] & 0x3f
						t_mode = packet_read[b+1]
						t_data = packet_read[b+2]
						triplets.append(t_address | (t_mode << 6) | (t_data << 11))

					cur_page[(26, d)] = triplets

			# Level 1 rows
			for r in range(0, 24):
				packet_read = source.read(40)
				if len(packet_read) != 40:
					break

				if packet_read != bytes(b'\x20' * 40):
					cur_page[r] = packet_read
				else:
					print('Blank row', r)

			cur_page['subcode'] = subcode

			# Finished reading the subpage
			subcode += 1

			num_pages_left -= 1

			if num_pages_left != 0:
				# More subpages coming up, skip over the 40 byte buffer and 2 byte terminator
				postamble = source.read(42)
				if len(postamble) != 42:
					break

				pages.append({})
				cur_page = pages[-1]
				cur_page['control_bits'] = set()

		if source_is_file:
			source.close()

		return pages
