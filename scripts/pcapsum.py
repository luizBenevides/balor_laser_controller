#!/usr/bin/env python3
import threading
import time
import pickle
import dpkt
import sys
import collections
sequence = []

first_packet = -1 if len(sys.argv) < 5 else int(sys.argv[3],16)
last_packet = -1 if len(sys.argv) < 5 else int(sys.argv[4],16)

#query_repeats = collections.defaultdict(int)
#response_repeats = collections.defaultdict(int)
last_query = None
last_response = collections.defaultdict(int)
query_repeats = 0
response_repeats = 0

for n,(ts, buf) in enumerate(dpkt.pcap.Reader(open(sys.argv[1],'rb'))):
    hos=buf[16]
    bus = buf[17]
    dvc = buf[19]
    endpoint = buf[21]&0x7F
    direc = buf[21]&0xF0
    data = buf[27:]
    if not data: continue
    if not endpoint or endpoint == 1: continue
    if n < first_packet: continue

    print ("     0x%08X dev.%d %s: %d bytes"%(n, endpoint, ' in' if direc else 'out', len(data) ))
    if direc: # input
        sequence.append((True, endpoint|direc, data))
        print (" IN:", ' '.join(['%02X'%x for x in data]))
        if data != last_response[last_query]:
            print ("##### This was a different response to query", ' '.join(['%02X'%x for x in last_query]))
        last_response[last_query] = data
    else:
        sequence.append((False, endpoint|direc, data))
        print ("OUT:", ' '.join(['%02X'%x for x in data]), '' if data[0] in [0x25, 0x07, 0x19, 0x01] else '!!', query_repeats, "reps of %02X"%last_query[0] if last_query else '')
        if data == last_query: 
            query_repeats += 1
        else:
            query_repeats = 0
        last_query = data
    print ("")
    if n == last_packet: break
#pickle.dump(sequence, open(sys.argv[2], 'wb'))

