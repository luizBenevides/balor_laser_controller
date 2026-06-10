#!/usr/bin/env python3
import balor
import sys, argparse
import time
parser = argparse.ArgumentParser(description='''
Interface with a Beijing JCZ Technology laser engraver.
This program uploads a file in the machine-specific binary format of
the particular laser engraving/marking/cutting machine and executes
it on the hardware. The machine-specific binary file will have been
prepared previously with accompanying converters.''',
epilog='''
NOTE: This software is EXPERIMENTAL and has only been tested with a
single machine. There are many different laser engraving machines 
and the fact that they look the same, or even have the same markings,
is not proof that they are really the same. IT COULD DAMAGE YOUR
MACHINE. Also, there is almost no error checking and if you feed this 
program garbage data there is no telling what will happen when it is
sent to the engraver. There is NO WARRANTY. And what happens when you
screw up and upload a data file made for lighting as a mark operation, 
or the other way around? I don't know, but IT MIGHT BE BAD! This is
without getting into the fact that the core purpose of this program is
causing a machine to emit pulses of light that can turn
metal into plasma and all the potential hazards associated with that,
which which you, as the owner of such a machine, should already be
very familiar.''')

#parser.add_argument('-m', '--machine', help="specify which machine interface to use. Valid machines: "+', '.join([x.__name__ for x in balor.all_known_machines]), default="BJJCZ_LMCV4_FIBER_M")
parser.add_argument('-i', '--index', help="specify which machine to use, if there is more than one", type=int, default=0)
parser.add_argument('-f', '--file', help="filename to load, in the machine-specific binary format (default stdin)", default=None)
parser.add_argument('-r', '--repeat', type=int, help="how many times to repeat the pattern (default run once); 0 means loop indefinitely (e.g. for lighting.)", default=1)
parser.add_argument('-v', '--verbose', type=int, help="verbosity level", default=0)
parser.add_argument('-c', '--correction-file', help="on-machine correction file to load (not to be confused with calfile)", default=None)

args = parser.parse_args()

if args.file is None:
    data = sys.stdin.buffer.read()
else:
    data = open(args.file,'rb').read()


import balor.sender
machine = balor.sender.Sender( )
#machine.set_verbosity(args.verbose)
if len(data)%machine.get_packet_size():
    print("The input file is not an even multiple of %d bytes long."%machine.packet_size, file=sys.stderr)
    sys.exit(-2)


import balor.command_list
commands = balor.command_list.CommandBinary(data, repeat=(args.repeat==args.repeat if args.repeat else float('inf')))
machine.open(machine_index=args.index, cor_file=args.correction_file)
machine.set_xy(0x8000, 0x8000)

try:
    machine.execute(command_list=commands, loop_count=args.repeat if args.repeat else float('inf'))
finally:
    machine.abort() 
    machine.close()


