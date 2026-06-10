#!/usr/bin/env python3
import sys
import numpy as np
import matplotlib.pyplot as plt

calfile = [h.split() for h in open(sys.argv[1], 'r').readlines()]
mcal = np.asarray([(float(h[0]), float(h[1])) for h in calfile])
gcal = np.asarray([(int(h[4],16), int(h[5],16)) for h in calfile])
ncal = np.asarray([(int(h[2]), int(h[3])) for h in calfile])

mm_x, mm_y, g_x, g_y = mcal[:,0], mcal[:,1], gcal[:,0], gcal[:,1]

#print ("X", list(g_x))
#print ("X", list(mm_x))
print ("Data for linear: X= %.2f : %.2f, Y= %.2f : %.2f"%(mm_x[31], mm_x[49], mm_y[39], mm_y[41]))
print ("Data for linear: X= %04X : %04X, Y= %04X : %04X"%(g_x[31], g_x[49], g_y[39], g_y[41]))
linear_x = (mm_x[49] - mm_x[31]) / (g_x[49] - g_x[31])
linear_y = (mm_y[41] - mm_y[39]) / (g_y[41] - g_y[39])
print ("Linear approxmation: %.3f um/gu X; %.3f um/gu Y"%(linear_x*1000.0, linear_y*1000.0))

lin_mm_x = (g_x-0x8000) * linear_x
lin_mm_y = (g_y-0x8000) * linear_y

u = lin_mm_x - mm_x
v = lin_mm_y - mm_y

anomaly_threshold = 1.5
colors = [0] * len(u)
anomaly_count = 1
for n,dx in enumerate(u):
    if dx > anomaly_threshold: 
        print ("Anomaly (%d,%d), %f X %d. %.02f >< %.02f"%(
            ncal[n][0],ncal[n][1], dx, n, mm_x[n], lin_mm_x[n]))
        colors[n] = anomaly_count
        anomaly_count += 1
for n,dy in enumerate(v):
    if dy > anomaly_threshold: 
        print ("Anomaly (%d,%d), %f Y %d. %.02f >< %.02f"%(
            ncal[n][0],ncal[n][1], dy, n, mm_y[n], lin_mm_y[n]))
        colors[n] = anomaly_count
        anomaly_count += 1

#colors = [0] * len(u)
#colors[58] = 2
#print (ncal[58])

plt.quiver(lin_mm_x, lin_mm_y, u, v, colors)
#plt.scatter(lin_mm_x, lin_mm_y)
#plt.scatter(mm_x, mm_y)
plt.show()

