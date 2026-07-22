#!/usr/bin/env python3
import balor
import sys, argparse, os, io, pickle

parser = argparse.ArgumentParser(description='''
Tool to convert a subset of SVG (scalable vector graphics) files to the 
machine-specific binary format used by Beijing JCZ galvo-based laser engravers.
This program produces raw bytestreams that can be sent by balor. SVG files
should not have any transforms or effects, and only paths will be converted
(e.g. no raster images, and no text - though text can just be converted to 
paths without incident.) You can also provide a settings file to associate
colors with engraver settings (q switch frequency, power, etc). Note: if this
is giving ValueErrors due to parameter overflow in travel/cut operations, 
your SVG file probably has group transforms (translate) that this program
ignores currently. (Basically, you just need to "flatten transforms.")''',
epilog='''
NOTE: This software is EXPERIMENTAL and has only been tested with a
single machine. There are many different laser engraving machines 
and the fact that they look the same, or even have the same markings,
is not proof that they are really the same.''')

parser.add_argument('operation', 
        help="choose operational mode (in lighting mode, a bounding box will be drawn.)", default="light", choices=["mark", "light"])

parser.add_argument('-f', '--file', 
        help="svg file to load.", default=None)

parser.add_argument('-o', '--output', 
    help="Specify the output file. (default stdout)",
    default=None)

parser.add_argument('-c', '--calfile',
    help="Provide a calibration file for the machine.")

parser.add_argument('-s', '--settings',
    help="Provide a settings file matching colors to machine settings.")


parser.add_argument('-m', '--machine', 
        help="specify which machine interface to use. Valid machines: "+', '.join(
            [x.__name__ for x in balor.all_known_machines]), default="BJJCZ_LMCV4_FIBER_M")

parser.add_argument('--travel-speed',
    help="Specify the traveling speed (mm/s)",
    default=2000, type=float)
parser.add_argument('--cut-speed',
    help="Specify the default cutting speed (mm/s)",
    default=800, type=float)
parser.add_argument('--laser-power',
    help="Specify the default laser power in percentage.",
    default=80, type=float)
parser.add_argument('--q-switch-frequency',
    help="Specify the default q switch frequency in KHz",
    default=30.0, type=float)
parser.add_argument('--laser-on-delay',
    help="EzCAD Start TC / laser on delay in microseconds",
    default=250, type=float)
parser.add_argument('--laser-off-delay',
    help="EzCAD Laser Off TC in microseconds",
    default=100, type=float)
parser.add_argument('--mark-end-delay',
    help="EzCAD End TC in microseconds",
    default=0, type=float)
parser.add_argument('--polygon-delay',
    help="EzCAD Polygon TC in microseconds",
    default=50, type=float)
parser.add_argument('--hatch-power-scale',
    help="Power multiplier used only for fill/hatch passes; stroke keeps pen power",
    default=1.0, type=float)
parser.add_argument('--hatch-speed-scale',
    help="Speed multiplier used only for fill/hatch passes; stroke keeps pen speed",
    default=1.0, type=float)
parser.add_argument('--hatch-overrun',
    help="Extra millimeters added before/after each hatch segment to stabilize marking inside the vector",
    default=0.0, type=float)
parser.add_argument('--hatch-serpentine',
    help="Keep the laser on while drawing adjacent hatch lines inside the same filled region",
    action='store_true')
parser.add_argument('--repetition', '-r',
    help="Specify the default number of passes. The file will be repeated from the first G00 movement.",
    default=10, type=int)
parser.add_argument('--hatch-spacing',
    help="Specify the default hatching spacing in microns",
    default=40.0, type=float)
parser.add_argument('--hatch-angle',
    help="Specify the default hatching angle in degrees",
    default=45.0, type=float)
parser.add_argument('--hidden-tags', type=str, default="",
    help="Comma-separated list of SVG IDs to ignore during rendering")
parser.add_argument('--quiet', action='store_true',
    help="Suppress diagnostic stderr output while generating the binary job")
parser.add_argument('--segment-length',
    help="Maximum path segment length in mm",
    default=1.0, type=float)
parser.add_argument('--xscale',
    help="Scale the x coordinates by this factor (before translation)",
    default=1.0, type=float)
parser.add_argument('--yscale',
    help="Scale the y coordinates by this factor (before translation)",
    default=1.0, type=float)

parser.add_argument('-x', '--xoff',
    help="Add this value to all x coordinates (after scaling)",
    default=0.0, type=float)
parser.add_argument('-y', '--yoff',
    help="Add this value to all y coordinates (after scaling)",
    default=0.0, type=float)



args = parser.parse_args()
if args.quiet:
    class _QuietStderr:
        def write(self, data):
            return len(data or "")
        def flush(self):
            pass
    sys.stderr = _QuietStderr()
import numpy as np
def separate_points(path, seglen, xscale, yscale, xoff, yoff):
    points = []
    lastx, lasty = path[0].start.real, path[0].start.imag
    for segment in path:
        startx, starty = segment.start.real, segment.start.imag
        endx, endy = segment.end.real, segment.end.imag
        samples = max(2, 1+int(round(segment.length()/seglen)))
        ts = np.linspace(0, 1, samples)
        discontinuity = ( startx != lastx or starty != lasty )
        for t in ts:
            point = segment.point(t)
            points.append( (point.real*xscale + xoff, -point.imag*yscale + yoff, discontinuity))

            discontinuity = False
        lastx, lasty = endx, endy

    #print (repr(points), file=sys.stderr)
    return points

from svgpathtools import Line
def render_fill(path, job, cal, settings, args, fill_color):
    print ("$FILL", path.bbox(), path.iscontinuous() and path.isclosed(), file=sys.stderr)
    brush = settings.get(fill_color)
    hatch_power = max(0.0, min(100.0, brush[1] * args.hatch_power_scale))
    hatch_speed = max(1.0, brush[2] * args.hatch_speed_scale)
    job.set_frequency(brush[0])
    job.set_power(hatch_power)
    job.set_cut_speed(hatch_speed)
    print ("$HATCH_SETTINGS", f"freq={brush[0]}", f"power={hatch_power:.1f}", f"speed={hatch_speed:.1f}", file=sys.stderr)
    
    angle = brush[3]
    spacing = float(brush[4]) / 1000.0
    if spacing <= 0: return

    # Rotate path by -angle to do vertical hatching, then rotate back
    rot_path = path.rotated(-angle, origin=0j)
    xmin, xmax, ymin, ymax = rot_path.bbox()
    
    hatch_span = 0.2 + xmax - xmin
    hatch_count = max(1, int(np.ceil(hatch_span / spacing)))
    hatch_x = (xmin - 0.1) + (np.arange(hatch_count) + 0.5) * spacing
    sys.stderr.write(("|"*(len(hatch_x)//50)) + "\n")
    sys.stderr.flush()
    
    import cmath
    hatch_columns = []
    
    for n, x in enumerate(hatch_x):
        if not n % 50: 
            sys.stderr.write(".")
            sys.stderr.flush()
        line = Line(complex(x, ymin-0.1), complex(x, ymax+0.1))

        try: 
            base_intersects = rot_path.intersect(line)
        except ValueError:
            print ("Caution - ValueError in intersect calculation.", file=sys.stderr)
            continue
            
        intersects = []
        for ((_,seg,t0), (_,_,t1)) in base_intersects:
            p0 = line.point(t1)
            intersects.append(p0.imag) # Just need the Y coordinate
        
        intersects.sort()
        deduped = []
        for y in intersects:
            if not deduped or abs(y - deduped[-1]) > 1e-6:
                deduped.append(y)
        intersects = deduped

        def rot_back(px, py):
            rad = np.radians(angle)
            c = complex(px, py) * cmath.rect(1, rad)
            return c.real, c.imag

        column_segments = []
        for y0, y1 in zip(intersects[::2], intersects[1::2]):
            rx0, ry0 = rot_back(x, y0)
            rx1, ry1 = rot_back(x, y1)
            overrun = max(0.0, args.hatch_overrun)
            if overrun:
                dx = rx1 - rx0
                dy = ry1 - ry0
                length = (dx * dx + dy * dy) ** 0.5
                if length > 0:
                    ux = dx / length
                    uy = dy / length
                    rx0 -= ux * overrun
                    ry0 -= uy * overrun
                    rx1 += ux * overrun
                    ry1 += uy * overrun
            px0 = rx0 * args.xscale + args.xoff
            py0 = -ry0 * args.yscale + args.yoff
            px1 = rx1 * args.xscale + args.xoff
            py1 = -ry1 * args.yscale + args.yoff
            column_segments.append(((px0, py0), (px1, py1)))
        hatch_columns.append(column_segments)

    if args.hatch_serpentine:
        active_runs = {}

        def flush_run(run):
            if not run:
                return
            start, end = run[0]
            job.goto(*start)
            job.laser_control(True)
            job.draw_line(start[0], start[1], end[0], end[1])
            previous = end
            for seg_start, seg_end in run[1:]:
                d_start = (previous[0] - seg_start[0]) ** 2 + (previous[1] - seg_start[1]) ** 2
                d_end = (previous[0] - seg_end[0]) ** 2 + (previous[1] - seg_end[1]) ** 2
                if d_end < d_start:
                    seg_start, seg_end = seg_end, seg_start
                job.draw_line(previous[0], previous[1], seg_start[0], seg_start[1])
                job.draw_line(seg_start[0], seg_start[1], seg_end[0], seg_end[1])
                previous = seg_end
            job.laser_control(False)

        for column_segments in hatch_columns:
            live_keys = set()
            for span_index, segment in enumerate(column_segments):
                live_keys.add(span_index)
                active_runs.setdefault(span_index, []).append(segment)
            for span_index in list(active_runs.keys()):
                if span_index not in live_keys:
                    flush_run(active_runs.pop(span_index))
        for run in active_runs.values():
            flush_run(run)
    else:
        for column_segments in hatch_columns:
            for (px0, py0), (px1, py1) in column_segments:
                job.goto(px0, py0)
                job.laser_control(True)
                job.draw_line(px0, py0, px1, py1)
                job.laser_control(False)
    print ("... done.", file=sys.stderr)
           



    #job.change_settings(*settings.get(fill_color))


def render_stroke(path, job, cal, settings, args, stroke_color):
    
    length = path.length()
    points = separate_points(path, args.segment_length,
                                args.xscale, args.yscale, args.xoff, args.yoff)

    #points = [(c.real*args.xscale + args.xoff,c.imag*args.yscale + args.yoff
    #                        ) for c in [path.point(t) for t in ts]]
    brush = settings.get(stroke_color)
    job.set_frequency(brush[0])
    job.set_power(brush[1])
    job.set_cut_speed(brush[2])
    print ("Path", len(path), len(points), repr(path), file=sys.stderr)
    if not points:
        return
    for _ in range(brush[6]):
        ix,iy,_ = points[0]
        try:
            job.goto(ix,iy)
        except ValueError:
            print ("Not including this stroke path:", path, file=sys.stderr)
            break
        job.laser_control(True)
        for x,y, discon in points[1:]:
            if discon:
                job.laser_control(False)
                job.goto(x,y)
                job.laser_control(True)
            else:
                job.draw_line(ix,iy, x,y)
            ix,iy = x,y
        job.laser_control(False)

def render_stroke_light(path, job, cal, settings, args, stroke_color):
    length = path.length()
    num_points = int(round(path.length() / args.segment_length))
    if num_points < 2: num_points = 2
    ts = np.linspace(0,1,num_points)
    points = [(c.real*args.xscale + args.xoff, -c.imag*args.yscale + args.yoff
                            ) for c in [path.point(t) for t in ts]]
    
    if not points:
        return
    
    ix,iy = points[0]
    job.goto(*points[0])
    for x,y in points[1:]:
        job.draw_line(ix,iy, x,y, Op=balor.command_list.OpTravel)
        ix,iy = x,y


def render_svg(svg, job, cal, args, settings):
    paths, attributes, svg_attributes = svg

    job.ready()
    job.set_travel_speed(args.travel_speed) # units are 2mm/sec

    if args.operation == 'mark':
        job.set_cut_speed(args.cut_speed)
        job.set_power(args.laser_power)
        job.set_frequency(args.q_switch_frequency)
        job.set_laser_on_delay(args.laser_on_delay)
        job.set_laser_off_delay(args.laser_off_delay)
        job.set_polygon_delay(args.polygon_delay)
        job.set_laser_control_delays(args.mark_end_delay, args.mark_end_delay)
    
    job.raw_travel(0x8000, 0x8000)
    begin = job.position
    
    hidden_tags_list = [t.strip() for t in args.hidden_tags.split(',')] if args.hidden_tags else []
    
    for path, attribute in zip(paths, attributes):
        tag_id = attribute.get('id', 'no id')
        
        if tag_id in hidden_tags_list:
            print (f"Skipping hidden tag: {tag_id}", file=sys.stderr)
            continue
            
        print ("begin", tag_id, file=sys.stderr)
        fill_color = None
        stroke_color = None
        
        # Try direct attributes first
        if 'fill' in attribute:
            v = attribute['fill'].strip()
            if v == 'none': fill_color = None
            elif v == 'black': fill_color = 0
            elif v.startswith('#'): fill_color = int(v[1:], 16)
                
        if 'stroke' in attribute:
            v = attribute['stroke'].strip()
            if v == 'none': stroke_color = None
            elif v == 'black': stroke_color = 0
            elif v.startswith('#'): stroke_color = int(v[1:], 16)

        if 'style' in attribute:
            style = attribute['style'].split(';')
            for atr in style:
                if not atr or not ':' in atr: continue
                try:
                    k,v = atr.split(':')
                    v = v.strip()
                    if k == 'fill':
                        if v == 'none':
                            fill_color = None
                        elif v == 'black':
                            fill_color = 0
                        elif v.startswith('#'):
                            fill_color = int(v[1:], 16)
                    elif k == 'stroke':
                        if v == 'none':
                            stroke_color = None
                        elif v == 'black':
                            stroke_color = 0
                        elif v.startswith('#'):
                            stroke_color = int(v[1:], 16)
                except Exception as e:
                    print(f"Warning: Could not parse style attribute '{atr}': {e}", file=sys.stderr)

        if fill_color == None and stroke_color == None:
            # Fallback to default if no colors found, so something actually happens
            stroke_color = 0 

            
        if fill_color != None and args.operation == 'mark':
            brush = settings.get(fill_color)
            spacing = float(brush[4]) / 1000.0
            if spacing > 0:
                print ("rendering hatching of", attribute.get('id', 'no id'), file=sys.stderr)
                render_fill(path, job, cal, settings, args, fill_color)
            else:
                print ("rendering outline stroke (fallback from fill) of", attribute.get('id', 'no id'), file=sys.stderr)
                render_stroke(path, job, cal, settings, args, fill_color)
        
        if stroke_color != None:
            if args.operation == 'mark':
                print ("rendering marking stroke of", attribute.get('id', 'no id'), file=sys.stderr)
                render_stroke(path, job, cal, settings, args, stroke_color)
            else:
                print ("rendering lighting stroke of", attribute.get('id', 'no id'), file=sys.stderr)
                render_stroke_light(path, job, cal, settings, args, stroke_color)
        else:
            # In light mode, if we have no stroke but we have fill, we still want to see something
            if args.operation == 'light' and fill_color != None:
                print ("rendering lighting stroke (from fill) of", attribute.get('id', 'no id'), file=sys.stderr)
                render_stroke_light(path, job, cal, settings, args, fill_color)
                
        print ("finished", attribute.get('id', 'no id'), file=sys.stderr)
    if args.operation == 'light':
        end = job.position
        print ("Adding %d repetitions %d:%d"%(args.repetition, begin, end+1), file=sys.stderr)
        if args.repetition > 1: job.duplicate(begin,end+1,args.repetition-1)
        print ("Length of operations", len(job.operations), file=sys.stderr)
    job.goto(0.0,0.0)

class MachineSettings:
    def __init__(self, args):
        self.settings = {}
        # add default settings
        self.add(0,
                cut_speed = args.cut_speed,
                laser_power = args.laser_power,
                q_switch_frequency = args.q_switch_frequency,
                repeats = args.repetition,
                hatch_angle = args.hatch_angle,
                hatch_spacing = args.hatch_spacing,
                hatch_pattern = None)
    def add(self, color, cut_speed, laser_power, q_switch_frequency, repeats, 
            hatch_angle, hatch_spacing, hatch_pattern):
        self.settings[color] = (q_switch_frequency, laser_power, cut_speed, hatch_angle,
                hatch_spacing, hatch_pattern, repeats)

        print ("Pen 0x%06X:"%color,
                "qs_period=%.2fkHz; laser_power=%d%%; cut_speed=%d;\n\thatch_angle=%.2f deg; hatch_spacing=%.2f um; hatch_pattern='%s';\n\trepeats=%d"%self.settings[color], file=sys.stderr)
    def get(self, color=0):
        return self.settings.get(color, self.settings[0])
    def mine_settings(self, data):
        i = 0
        while i < len(data):
            i = data.find('!pen', i)
            j = data.find('</', i)
            if i == -1 or j == -1: break
            setting = data[i:j].split()[1:]
            self.add(int(setting[0], 16),
                    laser_power = float(setting[2]),
                    q_switch_frequency = float(setting[1]),
                    cut_speed = float(setting[3]),
                    repeats = int(setting[7]),
                    hatch_angle = float(setting[4]),
                    hatch_spacing = float(setting[5]),
                    hatch_pattern = setting[6])
            i = j+1
    def add_csv(self, data):
        for line in data.split('\n'):
            line = line.strip()
            if not line or line[0] == '#': continue
            setting = line.split()
            self.add(int(setting[0], 16),
                    laser_power = float(setting[2]),
                    q_switch_frequency = float(setting[1]),
                    cut_speed = float(setting[3]),
                    repeats = int(setting[7]),
                    hatch_angle = float(setting[4]),
                    hatch_spacing = float(setting[5]),
                    hatch_pattern = setting[6])

from svgpathtools import svg2paths2

import sys
in_file = svg2paths2(args.file)

if args.output is None:
    out_file = sys.stdout.buffer
else:
    out_file = open(args.output, 'wb')

import balor.command_list, balor.Cal
cal = balor.Cal.Cal(args.calfile)
settings = MachineSettings(args)
if args.settings:
    settings.add_csv(open(args.settings, 'r').read())
settings.mine_settings(open(args.file, 'r').read())

job = balor.command_list.CommandList(cal=cal)

render_svg(in_file, job, cal, args, settings)

out_file.write(job.serialize())
