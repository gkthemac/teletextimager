# teletextimager
teletextimager is a Python library which will take teletext packets and render a bitmap image of the resulting teletext page. It is supplied with a script which can be used from the command line to read a teletext file and write out bitmap image(s) of the pages within.

The library depends on the [Python Imaging Library](https://pillow.readthedocs.io/) to render and save the bitmaps.

## Development status
The library is under development. The internals are subject to change but the `teletextimager` command should work pretty much the same way.

Still to be implemented:
- Incremental and decremental flash within adaptive and passive objects.
- G0 and G2 characters placed by adaptive and passive objects in character sets other than Latin.
- Level 3.5 bold and italic text.

## Installation
To install use `pip install .` to copy the files into your Python site-packages, or alternatively `pip install -e .` will not copy the actual files but merely reference them if you wish to keep up to date with the latest git commits or do your own development. During the install pip should attempt to install the Python Imaging Library as a dependency.

# Using from the command line
teletextimager is a command line script which will read a single teletext file in TTI or EP1 format and output a bitmap image file of the resulting teletext page. It can output the image in any format that the Python Imaging Library supports.

If a teletext file has multiple subpages then by default only the first subpage will be rendered, or by including `%s` in the output filename *all* subpages will be rendered to separate image files. The `-s` option can be used to select a different subpage, this will write only one image file even if `%s` is in the output filename.

## Basic usage
`teletextimager INFILE [-o OUTFILE]`

`INFILE` is a teletext file. `OUTFILE` is the filename of the resulting image.

## Parameters
`INFILE`\
Filename of input teletext page, required parameter.

`-o, --outfile=OUTFILE`\
Filename of output image. The filename must end with a file extension of a format that the Python Imaging Library supports writing to. `png` or `gif` is recommended, the latter will be animated if flashing attributes are present in the page.

To write a separate image for each subpage include `%s` in the filename, this will be replaced with the four-digit subpage number in each image filename.

If this parameter is omitted [Image.show()](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.show) is called, if running this on a desktop environment it should show the image in a viewer. The image will *not* be saved but the viewer may offer its own way to save the image itself.

`-s, --subpage=SUBPAGE`\
Select one subpage within the TTI file to be rendered. Defaults to 1 which is the first subpage, or all subpages written to separate image files if `%s` is included in the output filename.

`-l, --level=LEVEL`\
Select a decoding level, must be `1`, `1.5`, `2.5` or `3.5`. The default is Level 2.5 unless the `-c` parameter is also specified where it will default to Level 1.5

`-c, --classic`\
Disable intepretation of black foreground, double width and double height attributes. When this parameter is specified the decoding level is set to Level 1.5 unless `-l 1` is also specified.

`--conceal`\
Hide text covered by "conceal" attribute. Otherwise the default is to reveal concealed text.

`--no-header`\
Do not render the header row.

`--no-flof`\
Do not render row 24. This row usually has Fastext links.
