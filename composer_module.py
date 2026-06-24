import os
from svgpathtools import svg2paths2

class SceneComposer:
    @staticmethod
    def compose_workspace(items, output_path, canvas_size=300):
        """
        items: list of dicts with structure:
        {
            'id': str,
            'file': str,
            'ox': float, 'oy': float,
            'sx': float, 'sy': float,
            'rot': float,
            'color': str,          # Optional hex color override
            'visible': bool,
            'preserve_ids': bool   # Keep original path IDs instead of grouping
        }
        """
        svg_content = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        v = canvas_size / 2
        svg_content += f'<svg width="{canvas_size}mm" height="{canvas_size}mm" viewBox="{-v} {-v} {canvas_size} {canvas_size}" xmlns="http://www.w3.org/2000/svg">\n'
        
        def _flatten_path(path, ox, oy, sx, sy, rot, orig_cx, orig_cy):
            """Apply the same transform stack used by the workspace directly to the path geometry."""
            try:
                transformed = path.translated(complex(-orig_cx, -orig_cy))
                if sx != 1 or sy != 1:
                    transformed = transformed.scaled(sx, sy)
                if rot:
                    transformed = transformed.rotated(rot)
                if ox or oy:
                    transformed = transformed.translated(complex(ox, -oy))
                return transformed
            except Exception:
                return path

        # Draw by explicit z-order when provided; higher values are rendered later (on top).
        for item in sorted(items, key=lambda it: float(it.get('z', 0))):
            if not item.get('visible', True):
                continue
                
            if not os.path.exists(item['file']):
                continue
                
            try:
                paths, attrs, _ = svg2paths2(item['file'])
            except:
                continue
                
            preserve_ids = item.get('preserve_ids', False)
            
            # Find bounding box to center custom SVGs
            orig_cx, orig_cy = 0, 0
            if not preserve_ids:
                min_x, max_x, min_y, max_y = float('inf'), float('-inf'), float('inf'), float('-inf')
                for p in paths:
                    bb = p.bbox()
                    min_x = min(min_x, bb[0]); max_x = max(max_x, bb[1])
                    min_y = min(min_y, bb[2]); max_y = max(max_y, bb[3])
                
                if min_x != float('inf'):
                    orig_cx = (min_x + max_x) / 2
                    orig_cy = (min_y + max_y) / 2
            
            fill_attr = f'fill="{item["color"]}"' if item.get("color") else ""

            ox = float(item.get('ox', 0))
            oy = float(item.get('oy', 0))
            sx = float(item.get('sx', 1))
            sy = float(item.get('sy', 1))
            rot = float(item.get('rot', 0))

            svg_content += f'  <g {fill_attr}>\n'

            for p, a in zip(paths, attrs):
                tp = _flatten_path(p, ox, oy, sx, sy, rot, orig_cx, orig_cy)
                d = tp.d()
                path_id = a.get('id', item['id']) if preserve_ids else item['id']
                
                # If color is forced at group level, we don't need path fill, but to be safe:
                path_fill = ""
                if not item.get("color") and "fill" in a:
                    path_fill = f'fill="{a["fill"]}"'
                if len(tp) > 0:
                    bb = tp.bbox()
                    print(f"[DEBUG][composer] item={item['id']} path={path_id} bbox={bb} z={item.get('z', 0)}")
                svg_content += f'    <path id="{path_id}" d="{d}" {path_fill} />\n'
                
            svg_content += f'  </g>\n'
            
        svg_content += '</svg>'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        return output_path
