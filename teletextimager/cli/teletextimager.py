#!/usr/bin/env python3

import argparse
import os
import re
import sys
import tempfile

from PIL import Image

from teletextimager import teletextreadtti, teletextdecoder, teletextrenderpil

def main():
	parser = argparse.ArgumentParser()

	def level_valid(value):
		try:
			return re.match('^1$|^[123][.-pP]?5$', value).group(0)
		except:
			raise argparse.ArgumentTypeError('Not a valid decoding level')

	parser.add_argument('infile', help='input TTI file')
	parser.add_argument('-o', '--outfile', help='output image filename')
	parser.add_argument('-s', '--subpage', type=int, help='select subpage in TTI file')
	parser.add_argument('-l', '--level', default='2.5', type=level_valid, help='set decoding level')
	parser.add_argument('-c', '--classic', action='store_true', help='disable black foreground and double width')
	parser.add_argument('--no-header', action='store_true', help='remove header row')
	parser.add_argument('--no-flof', action='store_true', help='remove row 24')
	args = parser.parse_args()

	if args.level == '1':
		level = '1'
	elif len(args.level) == 2:
		level = args.level[0] + '.' +  args.level[1]
	else: #elif len(args.level) == 3:
		level = args.level[0] + '.' +  args.level[2]

	if args.classic and level != '1':
		level = '1.5'

	# Create the reader
	# When we support more formats we'll add more readers to the library
	# and select which one to use here based on the file extension
	in_ext = os.path.splitext(args.infile)[1]
	if in_ext.lower() == '.tti' or in_ext.lower() == '.ttix':
		my_reader = teletextreadtti.TeletextReadTTI()
	else:
		sys.exit('Filename extension \'{0}\' not supported'.format(in_ext))

#	stdin disabled as we can't figure out the format without the extension
#	if args.infile == "-":
#		my_pages = my_reader.read(sys.stdin)
#	else:

	# The reader reads in a TTI file and returns a list, one item per subpage
	# Each item is a dictionary holding the packets of the subpage
	my_pages = my_reader.read(args.infile)

	# Remove header and FLOF rows if we were asked to
	if args.no_header:
		for s in my_pages:
			s.pop(0)

	if args.no_flof:
		for s in my_pages:
			s.pop(24)

	my_decoder = teletextdecoder.TeletextDecode()

	# If the '-o' option isn't given try to show the subpage using Image.show()
	# This behaviour may not be kept
	if args.outfile == None:
		if args.subpage == None:
			subpage = 1
		else:
			subpage = args.subpage
		my_decoder.decode(my_pages[subpage - 1], level = level, black_foreground = not args.classic, double_width = not args.classic)
		my_pil_render = teletextrenderpil.TeletextRenderPIL()
		im = my_pil_render.render(my_decoder, border=(24, 20))
		im = im.resize((int(im.width * 1.2), im.height))
		im.show()
		sys.exit(0)

	percent_s = args.outfile.find('%s') != -1

	if args.subpage != None:
		if args.subpage > len(my_pages):
			print('Warning: selected subpage {0} not found in input file'.format(args.subpage), file=sys.stderr)
			subpage_range = [len(my_pages) - 1]
		else:
			subpage_range = [args.subpage - 1]
	elif percent_s:
		subpage_range = range(len(my_pages))
	else:
		subpage_range = [0]

	for s in subpage_range:
		outfile = args.outfile

		# TODO this just counts the pages instead of reading the actual subcodes
		if percent_s:
			if len(my_pages) != 1:
				outfile = outfile.replace('%s', '{:04d}'.format(s+1))
			else:
				outfile = outfile.replace('%s', '0000')

		temp_file = None

		# Open the output file
		# If the file already exists write it to a temporary file first
		# so we can atomically overwrite the file when all is written
		if os.path.exists(outfile):
			try:
				temp_file = tempfile.NamedTemporaryFile(dir=os.path.dirname(outfile), delete=False)
			except OSError as e:
				print('Cannot write output file \'{0}\': error {1} {2}'.format(outfile, e.errno, e.strerror), file=sys.stderr)
				sys.exit(os.EX_OSFILE)
			outfile_name = temp_file.name;
		else:
			outfile_name = outfile
		try:
			outfile_obj = open(outfile_name, 'wb')
		except OSError as e:
			print('Cannot write output file \'{0}\': error {1} {2}'.format(outfile, e.errno, e.strerror), file=sys.stderr)
			sys.exit(os.EX_OSFILE)

		# Pass the subpage packets to the decoder object which will hold the results
		# as an agnostic grid of characters, colours, enlarged fragments etc
		my_decoder.decode(my_pages[s], level = level, black_foreground = not args.classic, double_width = not args.classic)

		# and then pass that result to the render which will give us the final image
		my_pil_render = teletextrenderpil.TeletextRenderPIL()
		im = my_pil_render.render(my_decoder, border=(24, 20))

		out_ext = os.path.splitext(outfile)[1]
		if out_ext.lower() == '.gif':
			im = im.resize((int(im.width * 1.2), im.height))
			if my_decoder.flash_present == 0:
				im.save(outfile_obj, format='gif')
			else:
				fl_im = [ ]

				if my_decoder.flash_present == 1: 
					render_frames = [3]
					durations = 500
				elif my_decoder.flash_present == 2:
					render_frames = [1, 2]
					durations = [167, 167, 166]
				elif my_decoder.flash_present == 3:
					render_frames = [1, 2, 3, 4, 5]
					durations = [167, 167, 166, 167, 167, 166]

				for f in render_frames:
					fl_im.append(my_pil_render.render(my_decoder, border=(24, 20), flash_phase=f))
					fl_im[-1] = fl_im[-1].resize((int(fl_im[-1].width * 1.2), fl_im[-1].height), resample = Image.Resampling.NEAREST)

				im.save(outfile_obj, format='gif', save_all=True, append_images=fl_im, transparency=8, disposal=2, duration=durations, loop=0, palette=my_decoder.get_palette())
		else:
			im = im.resize((int(im.width * 1.2), im.height))
			im.save(outfile_obj, format=out_ext[1:])

		outfile_obj.close()

		# All is written so now we can atomically replace the original file
		if temp_file != None:
			try:
				os.replace(outfile_name, outfile)
			except OSError as e:
				try:
					os.unlink(outfile_name)
				except:
					pass
				print('Cannot write output file \'{0}\': error {1} {2}'.format(outfile, e.errno, e.strerror), file=sys.stderr)
				sys.exit(os.EX_OSFILE)

if __name__ == '__main__':
	main()
