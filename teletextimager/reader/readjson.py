#!/usr/bin/env python3

import copy
import json

class TeletextReadJSON:
	def load_control(self, cur_page, control):
		'''
		Apply control bits named in the 'control' object of a Teletext Page Object
		to our teletext dictionary.

		Any bits set to True will be added to the 'control' set and any set
		to False will be removed from the set.

		A 'language' property will modify bits 12, 13 and 14.

		:param cur_page: The dictionary defining a teletext page.
			The 'control' key will be modified.
		:param control: A dictionary as read from a Teletext Page Objects JSON, of
			named keys with True or False values, except for the 'language' key which
			will have an integer value.
		'''
		control_name = {
			'erasePage': 4,
			'newsflash': 5,
			'subtitle': 6,
			'suppressHeader': 7,
			'update': 8,
			'interruptedSequence': 9,
			'suppressPage': 10
		}

		if not 'control' in cur_page:
			cur_page['control'] = set()

		for c in control_name:
			if c in control:
				if control[c] == True:
					cur_page['control'].add(c)
				else:
					cur_page['control'].discard(c)

		if 'language' in control:
			for b in range(3):
				t = 1 << b
				if control['language'] & t == t:
					cur_page['control'].add(12 + b)
				else:
					cur_page['control'].discard(12 + b)

	def load_packets(self, cur_page, packets):
		'''
		Add packets in the 'packets' object of a Teletext Page Object to our
		teletext dictionary.

		:param cur_page: The dictionary defining a teletext page.
			The dictionary will be added to, with integer keys holding X/0-X/25 and
			tuples of two integers holding X/26-X28.
		:param packets: A list as read from a Teletext Page Objects JSON, of dictionaries
			describing packet numbers, designation codes and contents of packets.
		'''
		for pkt in packets:
			pkt_no = pkt['number']
			# 'text' and 'hamming' properties don't use 'dc'
			if 'text' in pkt:
				cur_page[pkt_no] = pkt['text'].encode()
				continue
			elif 'hamming' in pkt:
				cur_page[pkt_no] = pkt['hamming']
				continue

			desig_no = pkt.get('dc', 0)

			if 'triplets' in pkt:
				if pkt_no > 25:
					cur_page[(pkt_no, desig_no)] = pkt['triplets']
				else:
					cur_page[pkt_no] = pkt['triplets']
					cur_page[pkt_no].append(desig_no)
			elif 'linking' in pkt and pkt_no == 27 and desig_no < 4:
				# Init packet to mostly 0xf's as page xFF:3F7F means no page is specified
				fl_packet = [0xf] * 40
				fl_packet[0] = 0x0  # Designation code
				fl_packet[38] = 0x0 # CRC word
				fl_packet[39] = 0x0 # CRC word

				# Page numbers in Page Objects reference absolute magazine number
				# Convert to relative by XORing with page magazine number
				if 'number' in cur_page:
					mag_flip = cur_page['number'] & 0x700
				else:
					mag_flip = 0

				for i in range(6):
					if 'page' in pkt['linking']['links'][i]:
						link_rel = (int(pkt['linking']['links'][i]['page'], 16) & 0x7ff) ^ mag_flip

						if 'subcode' in pkt['linking']['links'][i]:
							subcode = int(pkt['linking']['links'][i]['subcode'], 16)
						else:
							subcode = 0x3f7f

						fl_packet[i*6+1] = link_rel & 0x00f
						fl_packet[i*6+2] = (link_rel & 0x0f0) >> 4
						fl_packet[i*6+3] = subcode & 0x000f
						fl_packet[i*6+4] = ((subcode >> 4) & 0x7) | ((link_rel & 0x100) >> 5)
						fl_packet[i*6+5] = (subcode >> 8) & 0xf
						fl_packet[i*6+6] = ((subcode >> 12) & 0x3) | ((link_rel & 0x600) >> 7)

				fl_packet[37] = pkt['linking'].get('linkControl', 15)

				cur_page[(pkt_no, desig_no)] = fl_packet

	def read(self, source):
		source_is_file = False
		if not hasattr(source, 'read'):
			source = open(source)
			source_is_file = True

		json_data = json.load(source)

		# The entire data was read all at once, so we can close the file now
		if source_is_file:
			source.close()

		pages = [ ]

		# All Teletext Page Object files must have a 'subpages' array
		# Return an empty list if that array is not there
		# TODO should we return None or throw an exception in this case?
		if not 'subpages' in json_data:
			return pages

		# Holds properties common to all pages: page number, control bits and cycle times
		parent_props = { }
		# Holds root page packets that'll be merged into each subpage (unless inherit is false)
		parent_packets = { }

		# Get properties from the root
		if 'number' in json_data:
			parent_props['number'] = int(json_data['number'], 16)

		if 'metadata' in json_data:
			if 'cycleSeconds' in json_data['metadata']:
				parent_props.setdefault('metadata', {})
				parent_props['metadata']['cycle_seconds'] = json_data['metadata']['cycleSeconds']

			if 'cycleCycles' in json_data['metadata']:
				parent_props.setdefault('metadata', {})
				parent_props['metadata']['cycle_cycles'] = json_data['metadata']['cycleCycles']

		# Get default control bits from the root
		if 'control' in json_data:
			self.load_control(parent_props, json_data['control'])

		# Get default packets that'll be merged into inheriting subpages
		if 'packets' in json_data:
			self.load_packets(parent_packets, json_data['packets'])

		for subpage in json_data['subpages']:
			# Append subpage that has the page number, control bits and cycle times
			pages.append(copy.deepcopy(parent_props))
			# Now populate the new subpage with the default packets unless inherit is false
			if 'inherit' in subpage and subpage['inherit'] == False:
				pass
			else:
				pages[-1] |= parent_packets

			# Overwrite control bits from the subpage if any
			if 'control' in subpage:
				self.load_control(pages[-1], subpage['control'])

			# Merge in packets from the subpage
			if 'packets' in subpage:
				self.load_packets(pages[-1], subpage['packets'])

		# Put title into the first subpage metadata like the TTI loader does
		if 'metadata' in json_data:
			if 'title' in json_data['metadata']:
				pages[0].setdefault('metadata', {})
				pages[0]['metadata']['title'] = json_data['metadata']['title']

		return pages
