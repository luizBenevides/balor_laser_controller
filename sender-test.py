#!/usr/bin/env python3

import balor
import balor.sender
import balor.command_list
sender = balor.sender.Sender(cor_table=open("balor/default.cor",'rb').read())
sender.open()

import sys

import balor.Cal
machine = "BJJCZ_LMCV4_FIBER_M"
calfile = "cal_0002.csv"
cal = balor.Cal.Cal(calfile)

def tick(job, loop_index):
    import numpy as np
    job.clear()
    job.set_travel_speed(8000) # 4000 mm/s
    x = 20*np.sin(0.1*loop_index)
    # make a triangle
    job.draw_line(0+x,0, 20+x, 20, Op=balor.command_list.OpTravel)
    job.draw_line(20+x,20, 0+x, 20, Op=balor.command_list.OpTravel)
    job.draw_line(0+x,20, 0+x, 0, Op=balor.command_list.OpTravel)
    if loop_index==99: print ("Loop finished")

import threading
import time

x, y = sender.raw_get_xy_position()
c = sender.get_condition()
print ("Initial Condition: 0x%04X   X: 0x%04X  Y: 0x%04X"%(c,x,y))


job = sender.job(tick=tick, cal=cal)

print ("Enter 'a' to abort, 's' to start.")
while 1:
    c = sender.get_condition()
    print ("Condition: 0x%04X"%c)
    

    cmd = sys.stdin.readline().split()
    if 'a' in cmd:
        sender.abort()
    if 's' in cmd:
        threading.Thread(target=lambda: job.execute(100)).start()


