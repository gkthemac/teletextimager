#!/usr/bin/env python3

import copy
from enum import Enum

class TeletextDecode:
	def __init__(self):
		self.level = 3
		self.status_bits = 0
		self.cells = [[self.Cell() for c in range(72)] for r in range(25)]
#		self.clear_page()

	class Frag(Enum):
		NORMALSIZE = 0
		DH_TOPHALF = 1
		DH_BOTTOMHALF = 2
		DW_LEFTHALF = 3
		DW_RIGHTHALF = 4
		DS_TOPLEFTQUARTER = 5
		DS_TOPRIGHTQUARTER = 6
		DS_BOTTOMLEFTQUARTER = 7
		DS_BOTTOMRIGHTQUARTER = 8

	class FlashAttr:
		def __init__(self):
			self.fl_mode = 0
			self.fl_rate_phase = 0
			self.fl_phase_shown = 0

	class DisplayAttr:
		def __init__(self):
			self.dheight = False
			self.dwidth = False
			self.box_win = False
			self.conceal = False
			self.invert = False
			self.und_sep = False

	class FontStyleAttr:
		def __init__(self):
			self.prop = False
			self.bold = False
			self.italic = False

	class Attribute:
		def __init__(self):
			self.foreground = 7
			self.background = 0
			self.flash = TeletextDecode.FlashAttr()
			self.display = TeletextDecode.DisplayAttr()
			self.font_style = TeletextDecode.FontStyleAttr()

	class CellChar:
		def __init__(self):
			self.ch_code = 0x20
			self.ch_set = 0
			self.ch_diacritic = 0

	class Cell:
		def __init__(self):
			self.ch = TeletextDecode.CellChar()
			self.attr = TeletextDecode.Attribute()
			self.frag = TeletextDecode.Frag.NORMALSIZE

	def get_char_code(self, r, c):
		return chr(self.cells[r][c].ch.ch_code)

	def get_char_set(self, r, c):
		return self.cells[r][c].ch.ch_set

	def get_char_diacritic(self, r, c):
		return self.cells[r][c].ch.ch_diacritic

	def get_foreground(self, r, c):
		result = self.cells[r][c].attr.foreground
		if result == 8:
			return(self.transparent(r, c))
		else:
			return result

	def get_background(self, r, c):
		result = self.cells[r][c].attr.background
		if result == 8:
			return(self.transparent(r, c))
		else:
			return result

	def get_flash_foreground(self, r, c):
		result = self.cells[r][c].attr.foreground ^ 8
		if result == 8:
			return(self.transparent(r, c))
		else:
			return result

	def get_fragment(self, r, c):
		return self.cells[r][c].frag

	def get_flash_mode(self, r, c):
		return self.cells[r][c].attr.flash.fl_mode

	def get_flash_rate_phase(self, r, c):
		return self.cells[r][c].attr.flash.fl_rate_phase

	def get_flash_phase_shown(self, r, c):
		return self.cells[r][c].attr.flash.fl_phase_shown

	def get_conceal(self, r, c):
		return self.cells[r][c].attr.display.conceal

	def get_invert(self, r, c):
		return self.cells[r][c].attr.display.invert

	def get_und_sep(self, r, c):
		return self.cells[r][c].attr.display.und_sep

	def get_flash_present(self):
		return self.flash_present

	def get_palette(self):
		result = []
		for i in range(32):
			r = (self._palette[i] & 0xf00) >> 8
			g = (self._palette[i] & 0x0f0) >> 4
			b = self._palette[i] & 0x00f
			result.append((r << 4) | r)
			result.append((g << 4) | g)
			result.append((b << 4) | b)
		return result

	@staticmethod
	def triplet_split(triplet):
		t_address = triplet & 0x3f
		t_mode = (triplet >> 6) & 0x1f
		t_data = triplet >> 11
		# Add 0x20 to mode of column triplets to simplify switch'ing
		if t_address < 40:
			t_mode |= 0x20

		return (t_address, t_mode, t_data)

	class Invocation:
		def __init__(self, page, y, d, t, org_r = 0, org_c = 0):
			self.enhancements = {}
			self.invokes = []
			self.org_r = org_r
			self.org_c = org_c

			self.act_r = 0
			self.act_c = 0
			self.org_mod_r = 0
			self.org_mod_c = 0

			first_triplet = True

			while True:
				if y < 26:
					if not y in page:
						break
					next_triplet = page[y][t];
				else:
					if not (y, d) in page:
						break
					next_triplet = page[(y, d)][t]

				if next_triplet != None:
					t_address, t_mode, t_data = TeletextDecode.triplet_split(next_triplet)

					# Stop at Termination Marker
					if t_mode == 0x1f and t_address == 0x3f:
						break
					# Object Definitions also mark the end of the current Object Definition
					if (t_mode == 0x15 or t_mode == 0x16 or t_mode == 0x17) and (not first_triplet):
						break

					self.map_triplet(t_address, t_mode, t_data)

				first_triplet = False

				# Move to next triplet
				t += 1
				if t == 13:
					t = 0
					if y < 26:
						y += 1
					else:
						d += 1
						if d == 16:
							break

		def address_to_row(self, address):
			if address == 40:
				return 24
			else:
				return address - 40

	class Invocation1p5(Invocation):
		def map_triplet(self, t_address, t_mode, t_data):
			if t_mode == 0x04:  # Set Active Position
				new_row = self.address_to_row(t_address)
				if self.act_r < new_row:
					self.act_r = new_row
					self.act_c = 0
			elif t_mode == 0x07:  # Address row 0
				if self.act_r == 0 and self.act_c == 0 and t_address == 63:
					self.act_c = 8

			if t_address < self.act_c:
				return

			if t_mode == 0x22 or t_mode >= 0x2f:
				self.act_c = t_address
				self.enhancements.setdefault((self.org_r + self.act_r, self.org_c + self.act_c), []).append((t_mode, t_data))

	class Invocation2p5(Invocation):
		def map_triplet(self, t_address, t_mode, t_data):
			if t_mode == 0x00:  # Full screen colour
				if self.act_r == 0 and self.act_c == 0 and (t_data & 0x60) == 00:
					self.enhancements.setdefault((self.org_r,0), []).append((t_mode, t_data))
			elif t_mode == 0x01:  # Full row colour
				new_row = self.address_to_row(t_address)
				if self.act_r < new_row:
					self.act_r = new_row
					self.act_c = 0
					if (t_data & 0x60) == 0x00 or (t_data & 0x60) == 0x60:
						self.enhancements.setdefault((self.org_r + self.act_r, 0), []).append((t_mode, t_data))
			elif t_mode == 0x04:  # Set Active Position
				new_row = self.address_to_row(t_address)
				if self.act_r < new_row:
					self.act_r = new_row
					if t_data < 40:
						self.act_c = t_data
				elif self.act_r == new_row and self.act_c <= t_data:
					self.act_c = t_data
			elif t_mode == 0x07:  # Address row 0
				if self.act_r == 0 and self.act_c == 0 and t_address == 63:
					self.act_c = 8
					if (t_data & 0x60) == 0x00 or (t_data & 0x60) == 0x60:
						self.enhancements.setdefault((self.org_r + self.act_r, 0), []).append((t_mode, t_data))
			elif t_mode == 0x10:  # Origin modifier
				self.org_mod_r = t_address - 40
				self.org_mod_c = t_data
				return
			elif t_mode == 0x11 or t_mode == 0x12 or t_mode == 0x13:
				self.enhancements.setdefault((self.org_r + self.org_mod_r + self.act_r, self.org_c + self.org_mod_c + self.act_c), []).append((t_mode, t_data))
				self.invokes.append((self.org_r + self.org_mod_r + self.act_r, self.org_c + self.org_mod_c + self.act_c, t_address, t_mode, t_data))
			# All "row triplet" modes now accounted for
			# All column triplets set the Active Position column apart from the
			# reserved and PDC values, so exit the entire function here if they
			# are encountered
			elif t_mode == 0x24 or t_mode == 0x25 or t_mode == 0x26 or t_mode == 0x2a:
				# Still need to enforce "origin modifier only affects next triplet"
				self.org_mod_r = 0
				self.org_mod_c = 0
				return

			self.org_mod_r = 0
			self.org_mod_c = 0

			if t_mode < 0x20:
				return

			if t_address < self.act_c:
				return

			self.act_c = t_address

			self.enhancements.setdefault((self.org_r + self.act_r, self.org_c + self.act_c), []).append((t_mode, t_data))

	def clear_page(self):
		for r in range(25):
			for c in range(72):
				self.cells[r][c].ch.ch_code = 0x20
				self.cells[r][c].ch.ch_set = 0
				self.cells[r][c].ch.ch_diacritic = 0
				self.cells[r][c].attr = self.Attribute()
				self.cells[r][c].frag = self.Frag.NORMALSIZE
		self._palette = [
			0x000, 0xf00, 0x0f0, 0xff0, 0x00f, 0xf0f, 0x0ff, 0xfff,
			0x000, 0x700, 0x070, 0x770, 0x007, 0x707, 0x077, 0x777,
			0xf05, 0xf70, 0x0f7, 0xffb, 0x0ca, 0x500, 0x652, 0xc77,
			0x333, 0xf77, 0x7f7, 0xff7, 0x77f, 0xf7f, 0x7ff, 0xddd
		]
		self.full_screen = 0
		self.full_row = [0] * 25
		self.left_side_panel = 0
		self.right_side_panel = 0

	def find_objects(self, invoc, page, obj_type = 0):
		for i in invoc.invokes:
			org_r, org_c, it_address, it_mode, it_data = i
			# Check if (sub)Object type can be invoked by Object type we're within
			if (it_mode & 0x10) <= obj_type:
				continue
			if (it_address & 0x18) == 0x08:
				# Local Object
				obj_def_y = 26;
				obj_def_d = ((it_address & 0x01) << 3) | (it_data >> 4)
				obj_def_t = it_data & 0x0f
			else:
				continue
			# Check if the Object Definition triplet is there and if so,
			# - if the N0-N8 bits match
			# - if the object type is the same
			# - and if the object is required at this Level
			if (obj_def_y, obj_def_d) in page:
				if self.level == 3:
					level_filter = 0x10
				else:
					level_filter = 0x08
				ot_address, ot_mode, ot_data = TeletextDecode.triplet_split(page[(obj_def_y, obj_def_d)][obj_def_t])
				if it_data == ot_data and (it_address & 0x03) == (ot_address & 0x03) and (it_mode | 0x04) == ot_mode and (ot_address & level_filter) != 0:
					if it_mode == 0x11:
						self.act_invoc.append(self.Invocation2p5(page, obj_def_y, obj_def_d, obj_def_t, org_r, org_c))
						self.find_objects(self.act_invoc[-1], page, 1)
					elif it_mode == 0x12:
						self.adp_invoc.append(self.Invocation2p5(page, obj_def_y, obj_def_d, obj_def_t, org_r, org_c))
						self.find_objects(self.adp_invoc[-1], page, 2)
					elif it_mode == 0x13:
						self.pas_invoc.append(self.Invocation2p5(page, obj_def_y, obj_def_d, obj_def_t, org_r, org_c))

	def parse_char_enhancements(self, enhances):
		result = None

		for e in enhances:
			t_mode, t_data = e

			if t_data < 0x20:
				continue
			if t_mode == 0x21:  # G1 character
				result = (t_data, 24, None)
			elif t_mode == 0x22 or t_mode == 0x2b:  # G3 character
				result = (t_data, 26, None)
			elif t_mode == 0x29:  # G0 character
				result = (t_data, 0, None)
			elif t_mode == 0x2f:  # G2 character
				result = (t_data, 2, None)
			elif t_mode >= 0x30:  # G0 diacritic
				result = (t_data, 0, t_mode - 0x30)

		return result

	def parse_attr_enhancements(self, enhances, attr):
		changes = set()

		for e in enhances:
			t_mode, t_data = e

			if t_mode == 0x20 and t_data < 0x20:  # Foreground colour
				attr.foreground = t_data
				changes.add(0x20)
			elif t_mode == 0x23 and t_data < 0x20:  # Background colour
				attr.background = t_data
				changes.add(0x23)
			elif t_mode == 0x27:  # Additional flash functions
				attr.flash.fl_mode = t_data & 0x03
				attr.flash.fl_rate_phase = t_data >> 2
				if attr.flash.fl_rate_phase == 4 or attr.flash.fl_rate_phase == 5:
					attr.flash.fl_phase_shown = 0
				else:
					attr.flash.fl_phase_shown = attr.flash.fl_rate_phase
				changes.add(0x27)
			elif t_mode == 0x2c:  # Display attributes
				attr.display.dheight = (t_data & 0x01) == 0x01
				attr.display.box_win = (t_data & 0x02) == 0x02
				attr.display.conceal = (t_data & 0x04) == 0x04
				attr.display.invert = (t_data & 0x10) == 0x10
				attr.display.und_sep = (t_data & 0x20) == 0x20
				attr.display.dwidth = (t_data & 0x40) == 0x40
				changes.add(0x2c)

		return changes

	def parse_g0g2_enhancements(self, enhances):
		for e in enhances:
			t_mode, t_data = e

			if t_mode == 0x28: # Modified G0 and G2 character set
				return(t_data >> 3, t_data & 0x07)

		return None

	def enlarge_char(self, r, c, covered):
		if r > 22:
			dheight = False
		else:
			dheight = self.cells[r][c].attr.display.dheight

		# TODO side panel edges
		if c == 39:
			dwidth = False
		else:
			dwidth = self.cells[r][c].attr.display.dwidth

		if dheight:
			if dwidth:
				self.cells[r][c].frag = self.Frag.DS_TOPLEFTQUARTER
			else:
				self.cells[r][c].frag = self.Frag.DH_TOPHALF
		elif dwidth:
			self.cells[r][c].frag = self.Frag.DW_LEFTHALF
		else:
			self.cells[r][c].frag = self.Frag.NORMALSIZE

		if self.cells[r][c].frag == self.Frag.DH_TOPHALF:
			self.cells[r+1][c] = copy.deepcopy(self.cells[r][c])
			self.cells[r+1][c].frag = self.Frag.DH_BOTTOMHALF
			covered.add((r+1, c))
		elif self.cells[r][c].frag == self.Frag.DW_LEFTHALF:
			self.cells[r][c+1] = copy.deepcopy(self.cells[r][c])
			self.cells[r][c+1].frag = self.Frag.DW_RIGHTHALF
			covered.add((r, c+1))
		elif self.cells[r][c].frag == self.Frag.DS_TOPLEFTQUARTER:
			self.cells[r][c+1] = copy.deepcopy(self.cells[r][c])
			self.cells[r+1][c] = copy.deepcopy(self.cells[r][c])
			self.cells[r+1][c+1] = copy.deepcopy(self.cells[r][c])
			self.cells[r][c+1].frag = self.Frag.DS_TOPRIGHTQUARTER
			self.cells[r+1][c].frag = self.Frag.DS_BOTTOMLEFTQUARTER
			self.cells[r+1][c+1].frag = self.Frag.DS_BOTTOMRIGHTQUARTER
			covered.add((r, c+1))
			covered.add((r+1, c))
			covered.add((r+1, c+1))

	def decode(self, page, level='3.5', black_foreground=True, double_width=True):
		self.clear_page()

		# When given a character set Region and NOS, these dictionaries are used
		# to look up which row of the character bitmap to use.
		l1_char_map = {
			(0, 0): 12, (0, 1): 15, (0, 2): 22, (0, 3): 16, (0, 4): 14, (0, 5): 19, (0, 6): 11,
			(1, 0): 18, (1, 1): 15, (1, 2): 22, (1, 3): 16, (1, 4): 14,             (1, 6): 19,
			(2, 0): 12, (2, 1): 15, (2, 2): 22, (2, 3): 16, (2, 4): 14, (2, 5): 19, (2, 6): 23,
			(3, 5): 21, (3, 7): 20,
			(4, 0):  1, (4, 1): 15, (4, 2): 13, (4, 3): 17, (4, 4):  2, (4, 5):  3, (4, 6): 11,
			(6, 6): 23, (6, 7): 4,
			(8, 0): 12, (8, 4): 14, (8, 7): 5,
			(10, 5): 6, (10, 7): 5
		}
		g0_char_map = {
			(4, 0): 1, (4, 4): 2, (4, 5): 3,
			(6, 7): 4,
			(8, 7): 5,
			(10, 5): 6, (10, 7): 5
		}
		g2_char_map = {
			(4, 0): 8, (4, 4): 8, (4, 5): 8,
			(6, 7): 9,
			(8, 0): 10, (8, 4): 10, (8, 7): 10,
			(10, 5): 10, (10, 7): 10
		}

		start_attr = self.Attribute()

		default_region = page.get('region', 0)
		default_nos = 0
		if 12 in page['control_bits']:
			default_nos |= 1
		if 13 in page['control_bits']:
			default_nos |= 2
		if 14 in page['control_bits']:
			default_nos |= 4
		second_region = 0xf
		second_nos = 0x7

		self.full_screen = 0
		full_row_down = 0
		bbcs = False
		fground_map = 0
		bground_map = 0
		left_side_panel = 0
		right_side_panel = 0

		self.flash_present = 0

		local_enh = None
		self.act_invoc = []
		self.adp_invoc = []
		self.pas_invoc = []

		if level == '1':
			self.level = 0
		elif level == '1.5':
			self.level = 1
		elif level == '2.5':
			self.level = 2
		elif level == '3.5':
			self.level = 3

		if self.level >= 2:
			allow_black_foreground = True
			allow_double_width = True

			pres_des = None
			if (28, 0) in page:
				pres_des = 0
			elif self.level == 3 and (28, 4) in page:
				pres_des = 4

			if pres_des != None:
				pres = page[(28, pres_des)]

				if pres[0] != None:
					default_region = (pres[0] >> 10) & 0xf
					default_nos = (pres[0] >> 7) & 0x7
					second_region = pres[0] >> 14

				if pres[1] != None:
					second_nos = pres[1] & 0x7

				if pres[12] != None:
					self.full_screen = (pres[12] >> 4) & 0x1f
					full_row_down = (pres[12] >> 9) & 0x1f
					bbcs = (pres[12] & 0x4000) == 0x4000
					clut_remap = pres[12] >> 15
				else:
					clut_remap = 0

				if clut_remap == 0:
					fground_map = 0
					bground_map = 0
				elif clut_remap == 1:
					fground_map = 0
					bground_map = 8
				elif clut_remap == 2:
					fground_map = 0
					bground_map = 16
				elif clut_remap == 3:
					fground_map = 8
					bground_map = 8
				elif clut_remap == 4:
					fground_map = 8
					bground_map = 16
				elif clut_remap == 5:
					fground_map = 16
					bground_map = 8
				elif clut_remap == 6:
					fground_map = 16
					bground_map = 16
				elif clut_remap == 7:
					fground_map = 16
					bground_map = 24
				start_attr.foreground = fground_map | 7

				if pres[1] != None and (self.level == 3 or (pres[1] & 0x20) == 0x20):
					side_panel_cols = (pres[1] >> 6) & 0xf
					if (pres[1] & 0x8) == 0x8:
						if side_panel_cols == 0:
							self.left_side_panel = 16
						else:
							self.left_side_panel = side_panel_cols
					if (pres[1] & 0x10) == 0x10:
						self.right_side_panel = 16 - side_panel_cols

				# Fill in the palette from X/28/0 and X/28/4
				for d in [0, 4]:
					if not (28, d) in page:
						continue
					if d == 4 and self.level < 3:
						continue;

					pres = page[(28, d)]

					if d == 0:
						c = 16
					else:
						c = 0
					c_end = c + 15
					t = 1

					while True:
						if pres[t] != None and pres[t+1] != None:
							self._palette[c] = ((pres[t] >> 2) & 0xf00) | ((pres[t] >> 10) & 0x0f0) | (pres[t+1] & 0x00f)

						if c == c_end:
							break

						if pres[t+1] != None and pres[t+2] != None:

							self._palette[c+1] = ((pres[t+1] << 4) & 0xf00) | ((pres[t+1] >> 4) & 0x0f0) | ((pres[t+1] >> 12) & 0x00f)
							self._palette[c+2] = ((pres[t+1] >> 8) & 0x300) | ((pres[t+2] << 10) & 0xc00) | ((pres[t+2] << 2) & 0x0f0) | ((pres[t+2] >> 6) & 0x00f)

						c += 3
						t += 2
			if (26, 0) in page:
				local_enh = self.Invocation2p5(page, 26, 0, 0)
				self.find_objects(local_enh, page)
		else:
			allow_black_foreground = black_foreground
			allow_double_width = double_width

			if self.level == 1 and (26, 0) in page:
				local_enh = self.Invocation1p5(page, 26, 0, 0)

		l1_default_char_set = l1_char_map.get((default_region, default_nos), 12)
		l1_second_char_set = l1_char_map.get((second_region, second_nos), l1_default_char_set)
		g0_default_char_set = g0_char_map.get((default_region, default_nos), 0)
		g2_default_char_set = g2_char_map.get((default_region, default_nos), 7)

		# Level 2.5 limits the "modified G0/G2 character set designation" triplet
		# to two character sets. These variables are used to enforce that.
		second_g0g2_region = None
		second_g0g2_nos = None

		l1_dheight_found = False
		l1_bottom_half = False

		for r in range(25):
			pkt = page.get(r, bytes(b'\x20' * 40))

			self.full_row[r] = full_row_down
			if bbcs:
				start_attr.background = full_row_down
			else:
				start_attr.background = bground_map

			current_attr = copy.deepcopy(start_attr)

			l1_fground_col = 7
			l1_mosaics = False
			l1_sep_mosaics = False
			l1_hold_mosaics = False
			l1_hold_mosaic_ch = 0x20
			l1_hold_mosaic_sep = False
			l1_escape_switch = False

			l1_char_set = l1_default_char_set
			g0_char_set = g0_default_char_set
			g2_char_set = g2_default_char_set

			for c in range(72):
				# Get any local enhancements and/or active objects at this cell
				enhances = []
				for inv in self.act_invoc:
					if (r, c) in inv.enhancements:
						enhances.extend(inv.enhancements[(r, c)])
				if local_enh != None:
					if (r, c) in local_enh.enhancements:
						enhances.extend(local_enh.enhancements[(r, c)])

				# When starting this row, deal with X/26 attributes that affect the entire row
				if c == 0:
					for e in enhances:
						t_mode, t_data = e

						if t_mode == 0x00 and (t_data & 0x60) == 0x00:
							self.full_screen = t_data
							full_row_down = t_data
							self.full_row[r] = t_data
							if bbcs:
								start_attr.background = t_data
						elif t_mode == 0x01 or (t_mode == 0x07 and r == 0):
							self.full_row[r] = t_data & 0x1f
							if bbcs:
								start_attr.background = t_data & 0x1f
							if (t_data & 0x60) == 0x60:
								full_row_down = t_data & 0x1f

				# Reset attributes at start of row
				if c == 0:
					current_attr = copy.deepcopy(start_attr)
				# and when crossing into side panels, except background is full row colour
				elif c == 40 or c == 56:
					current_attr = copy.deepcopy(start_attr)
					current_attr.background = self.full_row[r]

				if c < 40 and r in page:
					l1_byte = pkt[c]
				else:
					l1_byte = 0x20

				# Level 1 set-at and "set-between" attributes
				if c < 40 and (not l1_bottom_half):
					if l1_byte == 0x09:  # Steady
						current_attr.flash.fl_mode = 0
						current_attr.flash.fl_rate_phase = 0
					elif l1_byte == 0x0a:  # End box
						# "Set-between" - requires two consecutive "end box" codes
						if c > 0 and pkt[c-1] == 0x0a:
							current_attr.display.box_win = False
					elif l1_byte == 0x0b:  # Start box
						# "Set-between" - requires two consecutive "start box" codes
						if c > 0 and pkt[c-1] == 0x0b:
							current_attr.display.box_win = True
					elif l1_byte == 0x0c:  # Normal size
						if current_attr.display.dheight or current_attr.display.dwidth:
							# Change of size resets hold mosaic character
							l1_hold_mosaic_ch = 0x20
							l1_hold_mosaic_sep = False
						current_attr.display.dheight = False
						current_attr.display.dwidth = False
					elif l1_byte == 0x18:  # Conceal
						current_attr.display.conceal = True
					elif l1_byte == 0x19:  # Contiguous mosaics
						# This spacing attribute cannot cancel an X/26 underlined/separated attribute
						if not current_attr.display.und_sep:
							l1_sep_mosaics = False
					elif l1_byte == 0x1a:  # Separated mosaics
						l1_sep_mosaics = True
					elif l1_byte == 0x1c:  # Black background
						current_attr.background = start_attr.background
					elif l1_byte == 0x1d:  # New background
						current_attr.background = l1_fground_col | bground_map
					elif l1_byte == 0x1e:  # Hold mosaics
						l1_hold_mosaics = True

				# X/26 attributes
				changes = self.parse_attr_enhancements(enhances, current_attr)
				# Cancelling separated mosaics with X/26 attribute
				# also cancels the Level 1 separated mosaic attribute
				if 0x2c in changes and not current_attr.display.und_sep:
					l1_sep_mosaics = False

				# Deal with "modified G0/G2 character set" triplet here
				mod_g0g2 = self.parse_g0g2_enhancements(enhances)
				if mod_g0g2 != None:
					change_region, change_nos = mod_g0g2
					new_region = None
					new_nos = None

					if self.level == 3 or (change_region == default_region and change_nos == default_nos) or (change_region == second_region and change_nos == second_nos):
						new_region = change_region
						new_nos = change_nos
					elif second_g0g2_region == None:
						new_region = change_region
						new_nos = change_nos
						second_g0g2_region = new_region
						second_g0g2_nos = new_nos
					if new_region != None:
						g0_char_set = g0_char_map.get((new_region, new_nos), 0)
						g2_char_set = g2_char_map.get((new_region, new_nos), 7)

				# Level 1 character
				if c < 40 and (not l1_bottom_half):
					self.cells[r][c].ch.ch_diacritic = 0  # could de-duplicate
					if l1_byte >= 0x20:
						self.cells[r][c].ch.ch_code = l1_byte
						# true on mosaic character - not on blast through alphanumerics
						if l1_mosaics and (l1_byte & 0x20) == 0x20:
							self.cells[r][c].ch.ch_set = 24 + int(l1_sep_mosaics or current_attr.display.und_sep)
							l1_hold_mosaic_ch = l1_byte
							l1_hold_mosaic_sep = l1_sep_mosaics
						else:
							self.cells[r][c].ch.ch_set = l1_char_set
					elif l1_hold_mosaics:
						self.cells[r][c].ch.ch_code = l1_hold_mosaic_ch
						self.cells[r][c].ch.ch_set = 24 + int(l1_hold_mosaic_sep)
						self.cells[r][c].ch.ch_diacritic = 0  # could de-duplicate
					else:
						self.cells[r][c].ch.ch_code = 0x20
						self.cells[r][c].ch.ch_set = 0
						self.cells[r][c].ch.ch_diacritic = 0  # could de-duplicate
				else:
					# In side panel or on bottom half of Level 1 double height row, no Level 1 characters here
					self.cells[r][c].ch.ch_code = 0x20
					self.cells[r][c].ch.ch_set = 0
					self.cells[r][c].ch.ch_diacritic = 0  # could de-duplicate

				# X/26 character
				x26_character = self.parse_char_enhancements(enhances)
				if x26_character != None:
					x26_ch_code, x26_ch_set, x26_ch_diacritic = x26_character
					# We'd modify x26_ch_set while in the middle of the if/elif
					# Assign it to another variable just in case...
					ch_set_if = x26_ch_set
					if ch_set_if == 0:
						x26_ch_set = g0_char_set
					elif ch_set_if == 2:
						x26_ch_set = g2_char_set
					elif ch_set_if == 24 and current_attr.display.und_sep == True:
						x26_ch_set = 25

					self.cells[r][c].ch.ch_code = x26_ch_code
					self.cells[r][c].ch.ch_set = x26_ch_set
					if x26_ch_diacritic != None:
						self.cells[r][c].ch.ch_diacritic = x26_ch_diacritic

				covered = False

				# Check for the left half of a double-width or double-size character
				# to the left and stretch it into this cell
				if c > 0:
					if self.cells[r][c-1].frag == self.Frag.DW_LEFTHALF:
						self.cells[r][c] = copy.deepcopy(self.cells[r][c-1])
						self.cells[r][c].frag = self.Frag.DW_RIGHTHALF
						covered = True
					elif self.cells[r][c-1].frag == self.Frag.DS_TOPLEFTQUARTER:
						self.cells[r][c] = copy.deepcopy(self.cells[r][c-1])
						self.cells[r][c].frag = self.Frag.DS_TOPRIGHTQUARTER
						covered = True

				# Check for the top half of a double-height or double-size character
				# above and stretch it into this cell
				if (not covered) and r > 0:
					prev_dheight = self.cells[r][c].attr.display.dheight
					prev_dwidth = self.cells[r][c].attr.display.dwidth

					if self.cells[r-1][c].frag == self.Frag.DH_TOPHALF:
						self.cells[r][c] = copy.deepcopy(self.cells[r-1][c])
						self.cells[r][c].frag = self.Frag.DH_BOTTOMHALF
						covered = True
					elif self.cells[r-1][c].frag == self.Frag.DS_TOPLEFTQUARTER:
						self.cells[r][c] = copy.deepcopy(self.cells[r-1][c])
						self.cells[r][c].frag = self.Frag.DS_BOTTOMLEFTQUARTER
						covered = True
					elif self.cells[r-1][c].frag == self.Frag.DS_TOPRIGHTQUARTER:
						self.cells[r][c] = copy.deepcopy(self.cells[r-1][c])
						self.cells[r][c].frag = self.Frag.DS_BOTTOMRIGHTQUARTER
						covered = True

					if covered:
						self.cells[r][c].attr.display.dheight = prev_dheight
						self.cells[r][c].attr.display.dwidth = prev_dwidth

				# Handle bottom half of a Level 1 double height row,
				# where the character on the top half is single height
				if (not covered) and l1_bottom_half and x26_character == None:
					self.cells[r][c] = copy.deepcopy(self.cells[r-1][c])
					self.cells[r][c].frag = self.Frag.NORMALSIZE
					self.cells[r][c].attr.display.dheight = False
					self.cells[r][c].attr.display.dwidth = False
					self.cells[r][c].ch.ch_code = 0x20
					self.cells[r][c].ch.ch_set = 0
					self.cells[r][c].ch.ch_diacritic = 0
					covered = True

				if current_attr.flash.fl_mode != 0:
					# Rotate incremental/decremental flash
					if current_attr.flash.fl_rate_phase == 4 or current_attr.flash.fl_rate_phase == 5:
						if current_attr.flash.fl_phase_shown == 0:
							flash_origin_c = c
						if current_attr.flash.fl_rate_phase == 4:
							current_attr.flash.fl_phase_shown = ((c - flash_origin_c) % 3) + 1
						else:  # elif current_attr.flash.fl_rate_phase == 5:
							current_attr.flash.fl_phase_shown = 3 - ((c + 2 - flash_origin_c) % 3)

					if current_attr.flash.fl_rate_phase == 0:
						self.flash_present |= 1
					elif current_attr.flash.fl_rate_phase <= 5:
						self.flash_present |= 2

				if not covered:
					# Cell is NOT covered by enlarged character, so apply the
					# attributes and adjust the size
					self.cells[r][c].attr = copy.deepcopy(current_attr)
					if current_attr.display.dheight:
						if current_attr.display.dwidth:
							self.cells[r][c].frag = self.Frag.DS_TOPLEFTQUARTER
						else:
							self.cells[r][c].frag = self.Frag.DH_TOPHALF
					elif current_attr.display.dwidth:
						self.cells[r][c].frag = self.Frag.DW_LEFTHALF

				# Level 1 set-after spacing attributes
				if c < 40 and (not l1_bottom_half):
					if (l1_byte == 0x00 and allow_black_foreground) or (l1_byte >= 0x01 and l1_byte <= 0x07):  # Alphanumeric and foreground colour
						l1_mosaics = False
						l1_fground_col = l1_byte
						current_attr.foreground = l1_fground_col | fground_map
						current_attr.display.conceal = False
						# Switch from mosaics to alpha resets hold mosaic character
						l1_hold_mosaic_ch = 0x20
						l1_hold_mosaic_sep = False
					elif (l1_byte == 0x10 and allow_black_foreground) or (l1_byte >= 0x11 and l1_byte <= 0x17):  # Mosaic and foreground colour
						l1_mosaics = True
						l1_fground_col = l1_byte & 0x07
						current_attr.foreground = l1_fground_col | fground_map
						current_attr.display.conceal = False
					elif l1_byte == 0x08:  # Flashing
						current_attr.flash.fl_mode = 1
						current_attr.flash.fl_rate_phase = 0
					elif l1_byte == 0x0d:  # Double height
						if (not current_attr.display.dheight) or current_attr.display.dwidth:
							# Change of size resets hold mosaic character
							l1_hold_mosaic_ch = 0x20
							l1_hold_mosaic_sep = False
						current_attr.display.dheight = True
						current_attr.display.dwidth = False
						l1_dheight_found = True
					elif l1_byte == 0x0e and allow_double_width:  # Double width
						if current_attr.display.dheight or (not current_attr.display.dwidth):
							# Change of size resets hold mosaic character
							l1_hold_mosaic_ch = 0x20
							l1_hold_mosaic_sep = False
						current_attr.display.dheight = False
						current_attr.display.dwidth = True
					elif l1_byte == 0x0f and allow_double_width:  # Double size
						if (not current_attr.display.dheight) or (not current_attr.display.dwidth):
							# Change of size resets hold mosaic character
							l1_hold_mosaic_ch = 0x20
							l1_hold_mosaic_sep = False
						current_attr.display.dheight = True
						current_attr.display.dwidth = True
						l1_dheight_found = True
					elif l1_byte == 0x1b:  # ESC/switch
						l1_escape_switch = not l1_escape_switch
						if l1_escape_switch:
							l1_char_set = l1_second_char_set
						else:
							l1_char_set = l1_default_char_set
					elif l1_byte == 0x1f:  # Release mosaics
						l1_hold_mosaics = False

			if l1_bottom_half:
				l1_bottom_half = False
			if l1_dheight_found:
				l1_bottom_half = True
				l1_dheight_found = False

		# Overlay adaptive objects
		for i in self.adp_invoc:
			# Get columns of leftmost and rightmost enhancements in each row of this object
			col_left = {}
			col_right = {}
			for l in i.enhancements.keys():
				r, c = l
				if not r in col_left:
					col_left[r] = c
				col_right[r] = c
			covered = set()
			for r in col_left:
				adp_attr = self.Attribute()
				changes = set()
				for c in range(col_left[r], col_right[r] + 1):
					if (r, c) in i.enhancements.keys():
						changes.update(self.parse_attr_enhancements(i.enhancements[(r, c)], adp_attr))
						x26_character = self.parse_char_enhancements(i.enhancements[(r, c)])
					else:
						x26_character = None
					# If an Adaptive Object changes the display attributes,
					# it can overlap any part of any size underlying character.
					# Otherwise it can only overlap the non-origin part of enlarged characters.
					if 0x2c in changes:
						self.cells[r][c].attr.display = copy.deepcopy(adp_attr.display)
						if not (r, c) in covered:
							self.enlarge_char(r, c, covered)
					elif self.cells[r][c].frag == self.Frag.DW_RIGHTHALF or self.cells[r][c].frag == self.Frag.DS_TOPRIGHTQUARTER:
						covered.add((r, c))

					if not (r, c) in covered:
						any_change = False
						if 0x20 in changes:
							self.cells[r][c].attr.foreground = adp_attr.foreground
							any_change = True
						if 0x23 in changes:
							self.cells[r][c].attr.background = adp_attr.background
							any_change = True
						if 0x27 in changes:
							self.cells[r][c].attr.flash = copy.deepcopy(adp_attr.flash)
							any_change = True
						if any_change:
							self.enlarge_char(r, c, covered)

					if x26_character != None and not (r, c) in covered:
						x26_ch_code, x26_ch_set, x26_ch_diacritic = x26_character
						if x26_ch_set == 2:
							x26_ch_set = g2_default_char_set
						elif x26_ch_set == 24 and adp_attr.display.und_sep:
							x26_ch_set = 25
						self.cells[r][c].ch.ch_code = x26_ch_code
						self.cells[r][c].ch.ch_set = x26_ch_set
						if x26_ch_diacritic != None:
							self.cells[r][c].ch.ch_diacritic = x26_ch_diacritic
						else:
							self.cells[r][c].ch_ch_diacritic = 0
						self.enlarge_char(r, c, covered)

				del adp_attr

		# Overlay passive objects
		for i in self.pas_invoc:
			covered = set()
			# Passive objects always start with default attributes
			pas_attr = self.Attribute()
			for l, e in i.enhancements.items():
				self.parse_attr_enhancements(e, pas_attr)
				x26_character = self.parse_char_enhancements(e)
				if x26_character != None and not l in covered:
					x26_ch_code, x26_ch_set, x26_ch_diacritic = x26_character
					if x26_ch_set == 2:
						x26_ch_set = g2_default_char_set
					elif x26_ch_set == 24 and pas_attr.display.und_sep:
						x26_ch_set = 25
					r, c = l
					self.cells[r][c].attr = copy.deepcopy(pas_attr)
					self.cells[r][c].ch.ch_code = x26_ch_code
					self.cells[r][c].ch.ch_set = x26_ch_set
					if x26_ch_diacritic != None:
						self.cells[r][c].ch.ch_diacritic = x26_ch_diacritic
					else:
						self.cells[r][c].ch_ch_diacritic = 0
					self.enlarge_char(r, c, covered)

			del pas_attr

	def transparent(self, r, c):
		transparent_page = (self.status_bits & 0x03) != 0x00

		if self.cells[r][c].attr.display.box_win != transparent_page:
			return 8

		if self.cells[r][c].frag == self.Frag.DH_BOTTOMHALF or self.cells[r][c].frag == self.Frag.DS_BOTTOMLEFTQUARTER or self.cells[r][c].frag == self.Frag.DS_BOTTOMRIGHTQUARTER:
			row_colour = self.full_row[r-1]
		else:
			row_colour = self.full_row[r]

		if row_colour == 8:
			return 8
		else:
			return row_colour
