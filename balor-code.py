#!/usr/bin/env python3
import balor
import balor.command_list
import balor.Cal
import sys, argparse, os, io, pickle
import PIL
import numpy as np
#import qrcode
import segno

parser = argparse.ArgumentParser(description='''
Tool to engrave barcodes (including 2D QR codes) using laser engravers
controlled by Beijing JCZ control boards supported by balor.
This program produces raw bytestreams that can be sent by balor.''',
epilog='''
NOTE: This software is EXPERIMENTAL and has only been tested with a
single machine. There are many different laser engraving machines 
and the fact that they look the same, or even have the same markings,
is not proof that they are really the same.''')

parser.add_argument('operation', 
        help="choose operational mode - light bounding box or real marking", 
        default="light", choices=["mark", "light"])

parser.add_argument('-i', '--input', 
        help="Information to write in the barcode. (default - read from stdin)", 
        default="00000000")
parser.add_argument('-f', '--format', 
        help="Barcode format to use", 
        default="qr")
parser.add_argument('--code-version', 
        help="Barcode version to use", 
        default=None, type=str)
parser.add_argument('--code-mask', 
        help="Barcode mask to use", 
        default=0, type=int)
parser.add_argument('--code-error', 
        help="Barcode error correction level to use", 
        default=None, type=str)
parser.add_argument('--code-force-micro', 
        help="Generate a micro QR code", 
        dest="code_micro", action='store_true')
parser.add_argument('--code-force-regular', 
        help="Generate a regular QR code", 
        dest="code_micro", action='store_false')
parser.set_defaults(code_micro=None)


parser.add_argument('--code-box-size', 
        help="Box size to use (in counts)", 
        default=2, type=int)
parser.add_argument('--code-border-size', 
        help="Border size to use (in boxes)", 
        default=1, type=int)
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
    help="X resolution (mm per count) of the bar code.",
    default=0.1, type=float)
parser.add_argument('--raster-y-res',
    help="X resolution (mm per count) of the bar code.",
    default=0.1, type=float)

args = parser.parse_args()

job = balor.command_list.CommandList(cal=balor.Cal.Cal(args.calfile))

outfile = sys.stdout.buffer if args.output is None else open(args.output, 'wb')
from PIL import Image
def make_qrcode(job, data, operation, x0, y0, xres,yres, 
        version, box_size, border_size, rotation,
        micro=None, error=None, boost_error=True, mask=0):
    #qr.add_data(data)

    if micro is None:
        qr = segno.make(data, mask=mask, error=error, boost_error=boost_error,
                    version=version)
    else:
        segno_make = segno.make_micro if micro else segno.make_qr
        print ("Micro?", micro, file=sys.stderr)
        qr = segno_make(data, mask=mask, error=error, boost_error=boost_error,
                    version=version)
    print ("Code format:",qr.designator, file=sys.stderr)
    # This is stupid, why doesn't it provide a matrix output?
    buff = io.BytesIO()
    qr.save(buff, kind='png', border=border_size, scale=box_size)
    img = Image.open(buff)
    img = img.rotate(rotation, expand=True, fillcolor=1)
    ary = np.array(img)
    #img.save("test-barcode.png")
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
    for iy in range(ary.shape[0]):
        job.goto(x0,y0 + iy * yres)
        ix = 0
        while ix < ary.shape[1]:
            px = ary[ix,iy]
            run = 1
            while ix+run < ary.shape[1] and ary[ix+run,iy] == px: 
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

    if args.format == 'qr':
        make_qrcode(job, args.input, args.operation,
            args.xoffs, args.yoffs, args.raster_x_res, args.raster_y_res,
            args.code_version,  
            args.code_box_size, args.code_border_size, args.rotation,
            args.code_micro, args.code_error, True, args.code_mask
            )
    else:
        print ("Unsupported barcode format", args.format, file=sys.stderr)
        sys.exit(-1)


    outfile.write(bytes(job))
    outfile.close()
