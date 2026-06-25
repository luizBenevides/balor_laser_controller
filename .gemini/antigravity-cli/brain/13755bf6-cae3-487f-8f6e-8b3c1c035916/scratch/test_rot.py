import cmath
import numpy as np

angle = 45.0
rad = np.radians(angle)

# Let's say we have a point P = (10, 20)
px, py = 10.0, 20.0
p = complex(px, py)

# Rotate by -45 degrees using svgpathtools' rotation formula:
# In svgpathtools, path.rotated(deg, origin) rotates by deg degrees counter-clockwise around origin.
# Specifically, it multiplies by e^(i * rad).
# So rotating by -45 degrees is:
p_rot = p * cmath.rect(1, np.radians(-angle))

# Now let's rotate back using rot_back:
px_rot, py_rot = p_rot.real, p_rot.imag
c_back = complex(px_rot, py_rot) * cmath.rect(1, np.radians(angle))

print(f"Original: ({px}, {py})")
print(f"Rotated by -45: ({px_rot:.4f}, {py_rot:.4f})")
print(f"Rotated back: ({c_back.real:.4f}, {c_back.imag:.4f})")
