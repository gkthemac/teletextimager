#!/usr/bin/env python3

from enum import Enum
import sys
if sys.version_info < (3, 10):
	from importlib_resources import files
else:
	from importlib.resources import files
from PIL import Image, ImageFont, ImageDraw

from teletextimager import teletextdecoder

class TeletextRenderPIL:
#	def __init__(self):
#		self.decoder = None
		# This default border size will make a 640x576 image which can be scaled to 768x576
#		self.border_lr = 80
#		self.border_tb = 38

	def render(self, decoder, border=(80, 38), flash_phase=0, reveal=False):
		self.tt_font = [None] * 28

		def load_font(n):
			font_filename = [
				# 0 - Latin G0 character set placed by X/26 enhancement
				'G0_latin',
				# 1-6 - Non-Latin G0 character sets
				'G0_sr_hr',  'G0_ru_bg', 'G0_uk', 'G0_el', 'G0_ar', 'G0_he',
				# 7-10 - G2 character sets
				'G2_latin', 'G2_cyr', 'G2_el', 'G2_ar',
				# 11-23 - Latin G0 sets with NOS
				'G0_NOS_cs_sk', 'G0_NOS_en', 'G0_NOS_et', 'G0_NOS_fr', 'G0_NOS_de', 'G0_NOS_it', 'G0_NOS_lv_lt',
				'G0_NOS_pl', 'G0_NOS_pt_es', 'G0_NOS_ro', 'G0_NOS_sr_hr_sl', 'G0_NOS_sv_fi_hu', 'G0_NOS_tr',
				# 24-26 - G1 and G3 mosaics sets
				'G1_con', 'G1_sep', 'G3',
				# 27 - G0 reduced height for diacriticals
				'G0_reduced'
			]
			if self.tt_font[n] == None:
				font_path = files('teletextimager.font-etsi').joinpath(font_filename[n] + '.pil')
				self.tt_font[n] = ImageFont.load(font_path)

		font_width = 12
		font_height = 20

		if type(border) is tuple:
			border_lr, border_tb = border
		else:
			border_lr = border
			border_tb = border

		im_width = font_width * (40 + decoder.left_side_panel + decoder.right_side_panel) + border_lr * 2
		im_height = font_height * 25 + border_tb * 2

		im = Image.new(mode='P', size=(im_width, im_height))

		im.putpalette(decoder.get_palette(), rawmode='RGB')
		im.info.update( { "transparency": 8 } ) 

		im_draw = ImageDraw.Draw(im)

		# Draw the top and bottom Full Screen Colours
		im_draw.rectangle(
			[0, 0, im_width - 1, border_tb - 1], fill=decoder.full_screen
		)
		im_draw.rectangle(
			[0, im_height - border_tb, im_width - 1, im_height - 1], fill=decoder.full_screen
		)

		for r in range(25):
			origin_y = border_tb + r * font_height;

			# Draw the left and right Full Row Colour for this row
			im_draw.rectangle(
				[0, origin_y, border_lr - 1, origin_y + font_height - 1],
				fill=decoder.full_row[r]
			)
			im_draw.rectangle(
				[im_width - border_lr - 1, origin_y, im_width - 1, origin_y + font_height - 1], fill=decoder.full_row[r]
			)

			for c in range(72):
				if c < 56:
					if c >= 40 + decoder.right_side_panel:
						continue
					origin_x = border_lr + (c + decoder.left_side_panel) * font_width
				else:
					dc = c - (72 - decoder.left_side_panel)
					if dc < 0:
						continue
					origin_x = border_lr + dc * font_width

				if decoder.get_conceal(r, c) and not reveal:
					char_code = ' '
					char_set = 0
					char_diacritic = 0
				else:
					# char_code may get changed to 0x00 on flash phase
					char_code = decoder.get_char_code(r, c)
					char_set = decoder.get_char_set(r, c)
					char_diacritic = decoder.get_char_diacritic(r, c)

				load_font(char_set)

				if not decoder.get_invert(r, c):
					foreground = decoder.get_foreground(r, c)
					background = decoder.get_background(r, c)
				else:
					foreground = decoder.get_background(r, c)
					background = decoder.get_foreground(r, c)

				if decoder.get_flash_mode(r, c) != 0:
					# Flashing cell, decide if phase in this cycle is on or off
					if decoder.get_flash_rate_phase(r, c) == 0:
						flash_phon = (flash_phase < 3) ^ (decoder.get_flash_mode(r, c) == 2)
					else:
						flash_phon = ((flash_phase == decoder.get_flash_phase_shown(r, c)-1) or (flash_phase == decoder.get_flash_phase_shown(r, c)+2)) ^ (decoder.get_flash_mode(r, c) == 2)

				# If flashing to adjacent CLUT select the appropriate foreground colour
				if decoder.get_flash_mode(r, c) == 3 and not flash_phon:
					foreground = decoder.get_flash_foreground(r, c)

				# If flashing mode is Normal or Invert, draw a space instead of a character on phase
				# Character 0x00 draws space without underline
				if (decoder.get_flash_mode(r, c) == 1 or decoder.get_flash_mode(r, c) == 2) and not flash_phon:
					char_code = 0x00

				# This becomes a character-size image if we can't draw the text directly.
				# This applies if...
				# - the character will be enlarged
				# - the character has a G0 diacritical mark added
				char_im = None

				diacritic_reduce = char_diacritic != 0 and ord(char_code) >= 0x41 and ord(char_code) <= 0x5a
				# Capital letter with G0 diacritical mark has a reduced height
				if diacritic_reduce:
					load_font(27)

				if char_diacritic != 0 or decoder.get_fragment(r, c) != decoder.Frag.NORMALSIZE:
					# Draw cell rectangle in background colour and put the foreground character on top
					char_im = Image.new(mode='P', size=(font_width, font_height))
					char_im_draw = ImageDraw.Draw(char_im)
					char_im_draw.rectangle([0, 0, font_width - 1, font_height - 1], background)
					if diacritic_reduce:
						char_set = 27
					if char_code != 0x00:
						char_im_draw.text((0, 0), char_code, foreground, font=self.tt_font[char_set])
					if char_diacritic != 0:
						# Diacritical marks come from the G2 Latin set
						load_font(7)
						char_im_draw.text((0, 0), chr(char_diacritic + 0x40), foreground, font=self.tt_font[7])

				if char_im == None:
					# Draw cell rectangle in background colour and put the foreground character on top
					im_draw.rectangle([origin_x, origin_y, origin_x + font_width - 1, origin_y + font_height - 1], background)
					if char_code != 0x00:
						im_draw.text((origin_x, origin_y), char_code, fill=foreground, font=self.tt_font[char_set])
						if decoder.get_und_sep(r, c) and char_set < 24:
							im_draw.rectangle([origin_x, origin_y + font_height - 2, origin_x + font_width - 1, origin_y + font_height - 1], foreground)
				else:
					if decoder.get_fragment(r, c) == decoder.Frag.NORMALSIZE:
						frag_im = char_im
					elif decoder.get_fragment(r, c) == decoder.Frag.DH_TOPHALF:
						enlarge_im = char_im.resize((font_width, font_height * 2))
						frag_im = enlarge_im.crop((0, 0, font_width, font_height))
					elif decoder.get_fragment(r, c) == decoder.Frag.DH_BOTTOMHALF:
						enlarge_im = char_im.resize((font_width, font_height * 2))
						frag_im = enlarge_im.crop((0, font_height, font_width, font_height * 2))
					elif decoder.get_fragment(r, c) == decoder.Frag.DW_LEFTHALF:
						enlarge_im = char_im.resize((font_width * 2, font_height))
						frag_im = enlarge_im.crop((0, 0, font_width, font_height))
					elif decoder.get_fragment(r, c) == decoder.Frag.DW_RIGHTHALF:
						enlarge_im = char_im.resize((font_width * 2, font_height))
						frag_im = enlarge_im.crop((font_width, 0, font_width * 2, font_height))
					elif decoder.get_fragment(r, c) == decoder.Frag.DS_TOPLEFTQUARTER:
						enlarge_im = char_im.resize((font_width * 2, font_height * 2))
						frag_im = enlarge_im.crop((0, 0, font_width, font_height))
					elif decoder.get_fragment(r, c) == decoder.Frag.DS_TOPRIGHTQUARTER:
						enlarge_im = char_im.resize((font_width * 2, font_height * 2))
						frag_im = enlarge_im.crop((font_width, 0, font_width * 2, font_height))
					elif decoder.get_fragment(r, c) == decoder.Frag.DS_BOTTOMLEFTQUARTER:
						enlarge_im = char_im.resize((font_width * 2, font_height * 2))
						frag_im = enlarge_im.crop((0, font_height, font_width, font_height * 2))
					elif decoder.get_fragment(r, c) == decoder.Frag.DS_BOTTOMRIGHTQUARTER:
						enlarge_im = char_im.resize((font_width * 2, font_height * 2))
						frag_im = enlarge_im.crop((font_width, font_height, font_width * 2, font_height * 2))

					im.paste(frag_im, (origin_x, origin_y))

					if char_code != 0x00 and decoder.get_und_sep(r, c) and decoder.get_char_set(r, c) < 24:
						if decoder.get_fragment(r, c) == decoder.Frag.NORMALSIZE or decoder.get_fragment(r, c) == decoder.Frag.DW_LEFTHALF or decoder.get_fragment(r, c) == decoder.Frag.DW_RIGHTHALF:
							im_draw.rectangle([origin_x, origin_y + font_height - 2, origin_x + font_width - 1, origin_y + font_height - 1], foreground)
						elif decoder.get_fragment(r, c) == decoder.Frag.DH_BOTTOMHALF or decoder.get_fragment(r, c) == decoder.Frag.DS_BOTTOMLEFTQUARTER or decoder.get_fragment(r, c) == decoder.Frag.DS_BOTTOMRIGHTQUARTER:
							im_draw.rectangle([origin_x, origin_y + font_height - 3, origin_x + font_width - 1, origin_y + font_height - 1], foreground)

		return im
