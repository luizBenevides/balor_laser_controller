from svgpathtools import svg2paths2
import numpy as np
import cmath

paths, attributes, svg_attributes = svg2paths2(r"C:\Users\paulo\Desktop\balor\temp_workspace.svg")

p = paths[0]
print("Original BBox:", p.bbox())

angle = 45.0
rot_path = p.rotated(-angle)
print("Rotated BBox:", rot_path.bbox())

# Let's check some points on rot_path and rotate them back
# Point on rot_path
p_rot_start = rot_path[0].start
rad = np.radians(angle)
p_back = p_rot_start * cmath.rect(1, rad)

print("Original start:", p[0].start)
print("Rotated start: ", p_rot_start)
print("Rotated back:  ", p_back)
