#!/usr/bin/env python3
import usb.core
import usb.util
import threading
import time
import pickle
import dpkt
import sys
#device = list(usb.core.find(find_all=True, idVendor=0x9588, idProduct=0x9899))[0]
#device.set_configuration()

sequence = []

first_packet = -1 if len(sys.argv) < 5 else int(sys.argv[3],16)
last_packet = -1 if len(sys.argv) < 5 else int(sys.argv[4],16)

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
        #reply = device.read(endpoint|direc, len(data), 1000)
        print (" IN:", ' '.join(['%02X'%x for x in data]))
    else:
        sequence.append((False, endpoint|direc, data))
        #assert device.write(endpoint|direc, data, 1000) == len(data)
        print ("OUT:", ' '.join(['%02X'%x for x in data]), '' if data[0] in [0x25, 0x07, 0x19, 0x01] else '!!')
    print ("")
    if n == last_packet: break
pickle.dump(sequence, open(sys.argv[2], 'wb'))

