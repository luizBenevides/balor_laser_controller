#!/usr/bin/env python3
import balor
import balor.command_list
import balor.Cal
import sys, argparse, os, io
import PIL
from PIL import ImageFont, ImageDraw, Image
import numpy as np

# Import our modular barcode generator
import barcode_module

parser = argparse.ArgumentParser(description='Balor Barcode Generator (Code 128 + Serial)')
parser.add_argument('operation', choices=['light', 'mark'], help="Operation to perform")
parser.add_argument('-i', '--input', help="Serial data to encode", required=True)
parser.add_argument('-o', '--output', help="Specify the output file", default=None)
parser.add_argument('-c', '--calfile', help="Provide a calibration file")
parser.add_argument('--text-pos', choices=['top', 'bottom'], default='bottom', help="Position of the serial text")
parser.add_argument('--travel-speed', default=2000, type=float)
parser.add_argument('--mark-speed', default=500, type=float)
parser.add_argument('--laser-power', default=50, type=float)
parser.add_argument('--q-switch-frequency', default=40.0, type=float)
parser.add_argument('-x', '--xoffs', default=0.0, type=float)
parser.add_argument('-y', '--yoffs', default=0.0, type=float)
parser.add_argument('--scale', default=1.0, type=float)
# Add unused args to avoid errors from GUI
parser.add_argument('--raster-x-res', type=float, default=0.1)
parser.add_argument('--raster-y-res', type=float, default=0.1)

args = parser.parse_args()

job = balor.command_list.CommandList(cal=balor.Cal.Cal(args.calfile))
outfile = sys.stdout.buffer if args.output is None else open(args.output, 'wb')

gen = barcode_module.BarcodeGenerator()
barcode_height = 15.0 # mm
sc = args.scale

# 1. Generate Barcode VECTORS (Best for quality)
vectors, total_width = gen.generate_code128_vectors(args.input, barcode_height=barcode_height)

# 2. Generate Text Image for the serial (Raster for simplicity of fonts)
font_size = 24
try:
    font = ImageFont.truetype("arial.ttf", font_size)
except OSError:
    font = ImageFont.load_default()

# Get text bbox
dummy_img = Image.new("1", (1, 1))
draw = ImageDraw.Draw(dummy_img)
bbox = draw.textbbox((0, 0), args.input, font=font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]

# Create text image
text_img = Image.new("1", (tw, th), color=1)
draw = ImageDraw.Draw(text_img)
draw.text((0, 0), args.input, font=font, fill=0)
text_img = text_img.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT)
text_ary = np.array(text_img)

# Layout constants
padding = 2.0 # mm
text_res = 0.08 # mm/pixel for text

if args.operation == 'light':
    job.light_on()
    job.set_travel_speed(args.travel_speed)
    # Draw bounding box for barcode + text
    full_w = max(total_width, tw * text_res) * sc
    full_h = (barcode_height + padding + th * text_res) * sc
    pts = [
        (args.xoffs, args.yoffs),
        (args.xoffs + full_w, args.yoffs),
        (args.xoffs + full_w, args.yoffs + full_h),
        (args.xoffs, args.yoffs + full_h),
        (args.xoffs, args.yoffs)
    ]
    job.init(pts[0][0], pts[0][1])
    for pt in pts:
        job.goto(pt[0], pt[1])
else:
    job.set_mark_settings(
        travel_speed=args.travel_speed,
        frequency=args.q_switch_frequency,
        power=args.laser_power,
        cut_speed=args.mark_speed,
        laser_on_delay=100,
        laser_off_delay=100,
        polygon_delay=10
    )
    
    # Calculate offsets
    barcode_y = 0 if args.text_pos == 'bottom' else (th * text_res + padding)
    text_y = (barcode_height + padding) if args.text_pos == 'bottom' else 0
    
    # Center text relative to barcode
    text_off_x = (total_width - (tw * text_res)) / 2
    if text_off_x < 0: text_off_x = 0
    
    # A. Mark Barcode VECTORS
    for v in vectors:
        x1, y1, x2, y2 = v
        job.goto(args.xoffs + x1 * sc, args.yoffs + (y1 + barcode_y) * sc)
        job.mark(args.xoffs + x2 * sc, args.yoffs + (y2 + barcode_y) * sc)
        
    # B. Mark Text RASTER
    tw_px, th_px = text_ary.shape
    for i in range(th_px):
        for j in range(tw_px):
            if text_ary[j, i] == 0:
                px = (i * text_res + text_off_x) * sc
                py = (j * text_res + text_y) * sc
                job.goto(args.xoffs + px, args.yoffs + py)
                job.mark(args.xoffs + px + text_res * sc, args.yoffs + py)

outfile.write(bytes(job))
outfile.close()
