#!/usr/bin/env python3
import pickle
import sys
import pprint


for arg in sys.argv[1:]:
    filename, name = arg.split(':') if ':' in arg else (arg,arg)
    sequence = pickle.load(open(filename, 'rb'))
    pp=pprint.PrettyPrinter(indent=4)
    sys.stdout.write(name+" = ")
    pp.pprint(sequence)

