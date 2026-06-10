#!/usr/bin/env python3
import balor
import balor.command_list
import balor.Cal
import sys, argparse, os, io, pickle
import PIL
from PIL import ImageFont, ImageDraw

import numpy as np

parser = argparse.ArgumentParser(description='''
Tool to engrave text using laser engravers controlled by Beijing JCZ control 
boards supported by balor. This program produces raw bytestreams that can be 
sent by balor.''',
epilog='''
NOTE: This software is EXPERIMENTAL and has only been tested with a
single machine. There are many different laser engraving machines 
and the fact that they look the same, or even have the same markings,
is not proof that they are really the same.''')

parser.add_argument('operation', 
        help="choose operational mode - light bounding box or real marking", 
        default="light", choices=["mark", "light"])

parser.add_argument('-i', '--input', 
        help="Information to write in the text. (default - read from stdin)", 
        default="00000000")
parser.add_argument('-f', '--font', 
        help=".ttf font to use", 
        default="arial")
parser.add_argument('--font-size', 
        help="Font size to use", 
        default=10, type=int)
parser.add_argument('--rotation', 
        help="Angle to rotate the text", 
        default=0, type=float)


parser.add_argument('-o', '--output', 
    help="Specify the output file. (default stdout)",
    default=None)

parser.add_argument('-c', '--calfile',
    help="Provide a calibration file for the machine.")

parser.add_argument('-m', '--machine', 
        help="specify which machine interface to use. Valid machines: "+', '.join(
            [x.__name__ for x in balor.all_known_machines]), default="BJJCZ_LMCV4_FIBER_M")

parser.add_argument('--travel-speed',
    help="Specify the traveling speed (mm/s)",
    default=2000, type=float)
parser.add_argument('--mark-speed',
    help="Specify the marking speed (mm/s)",
    default=500, type=float)
parser.add_argument('--laser-power',
    help="Specify the laser power in percentage.",
    default=50, type=float)
parser.add_argument('--q-switch-frequency',
    help="Specify the q switch frequency in KHz",
    default=40.0, type=float)

parser.add_argument('-x', '--xoffs',
    help="Specify an x offset for the image (mm.)",
    default=0.0, type=float)

parser.add_argument('-y', '--yoffs',
    help="Specify an y offset for the image (mm.)",
    default=0.0, type=float)

parser.add_argument('--raster-x-res',
    help="X resolution (mm per count) of the text.",
    default=0.1, type=float)
parser.add_argument('--raster-y-res',
    help="X resolution (mm per count) of the text.",
    default=0.1, type=float)

args = parser.parse_args()

job = balor.command_list.CommandList(cal=balor.Cal.Cal(args.calfile))

outfile = sys.stdout.buffer if args.output is None else open(args.output, 'wb')
from PIL import Image
def make_text(job, data, operation, x0, y0, xres,yres, 
        font, rotation):

    buff = io.BytesIO()
    img = Image.new("1", font.getbbox(data)[2:], color=1)
    draw = ImageDraw.Draw(img)
    draw.text((0,0), data, font=font)
    img = img.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT)
    img = img.rotate(rotation, fillcolor=1, expand=True)
    ary = np.array(img)

    img.save("test.png")

    w,h = ary.shape
    w *= xres
    h *= yres
    if operation == 'light': # just draw a box and be done
        for _ in range(32):
            job.draw_line(x0,y0, x0+w,y0, Op=balor.command_list.OpTravel)
            job.draw_line(x0+w,y0, x0+w,y0+h, Op=balor.command_list.OpTravel)
            job.draw_line(x0+w,y0+h, x0, y0+h, Op=balor.command_list.OpTravel)
            job.draw_line(x0,y0+h, x0,y0, Op=balor.command_list.OpTravel)
        return

    # mode - mark
    job.goto(x0,y0)
    for iy in range(ary.shape[1]):
        job.goto(x0,y0 + iy * yres)
        ix = 0
        while ix < ary.shape[0]:
            px = ary[ix,iy]
            run = 1
            while ix+run < ary.shape[0] and ary[ix+run,iy] == px: 
                run += 1
                #print (iy, ix, run, file=sys.stderr)
            
            y = y0 + iy * yres
            #x1 = x0 + ix * xres
            x = x0 + (ix + run) * xres
            if px:
                job.goto(x, y)
            else:
                job.laser_control(True)
                job.mark(x, y)
                job.laser_control(False)
            ix += run

if __name__ == '__main__':
    if args.operation == 'light':
        job.light_on()
        job.set_travel_speed(args.travel_speed)

    else:
        job.set_mark_settings(
            travel_speed = args.travel_speed,
            frequency = args.q_switch_frequency,
            power = args.laser_power,
            cut_speed = args.mark_speed,
            laser_on_delay = 0x0064,
            laser_off_delay = 0x0064,
            polygon_delay = 0x000A
            )
    try:
        font = ImageFont.truetype(args.font, args.font_size)
    except OSError:
        try:
            # Try arial as a safe bet on Windows
            font = ImageFont.truetype("arial.ttf", args.font_size)
        except OSError:
            # Fallback to default bitmapped font
            font = ImageFont.load_default()

    img = make_text(job, args.input, args.operation,
        args.xoffs, args.yoffs, args.raster_x_res, args.raster_y_res,
        font, args.rotation)


    outfile.write(bytes(job))
    outfile.close()
