import os
from svgpathtools import svg2paths2

svg_path = r"temp_workspace.svg"
if os.path.exists(svg_path):
    paths, attributes, svg_attributes = svg2paths2(svg_path)
    print(f"Total paths: {len(paths)}")
    ids = set()
    for attr in attributes:
        ids.add(attr.get('id', 'NO_ID'))
    print(f"Path IDs present in temp_workspace.svg: {ids}")
else:
    print("temp_workspace.svg not found")
