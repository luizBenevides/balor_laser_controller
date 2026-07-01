import os
os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.getcwd(), ".matplotlib-cache"))

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
import numpy as np

class BarcodeGenerator:
    def __init__(self, font_path="arial.ttf"):
        self.font_path = font_path

    def generate_code128_svg(self, data, output_path, barcode_height=20, text_pos="bottom",
                             barcode_w_scale=1.0, text_scale=1.0, text_x_off=0.0, text_y_off=0.0,
                             barcode_rot=0, text_rot=0, barcode_color="#000000", text_color="#000000",
                             barcode_type="code128", font_name=None, text_space=0.0, group=True):
        """
        Generates a barcode as an SVG file with vector paths for both bars AND text,
        supporting individual scaling, offsets, rotation, colors, fonts, types and text spacing.
        """
        # Negate angles to account for Y-down coordinate system in SVG
        barcode_rot = -barcode_rot
        text_rot = -text_rot

        # Select Barcode Class
        barcode_type_str = str(barcode_type).lower()
        if "gs1" in barcode_type_str or "ean" in barcode_type_str:
            try:
                EAN = barcode.get_barcode_class('gs1_128')
                it = EAN(data)
                code = it.to_ascii()
            except Exception as ex:
                print(f"[DEBUG] Falling back to code128 due to GS1 format error: {ex}")
                EAN = barcode.get_barcode_class('code128')
                it = EAN(data)
                code = it.to_ascii()
        else:
            EAN = barcode.get_barcode_class('code128')
            it = EAN(data)
            code = it.to_ascii()
            
        module_width = 0.4 * barcode_w_scale # Apply width scale
        total_width = len(code) * module_width
        
        def rotate_point(x, y, angle_deg, cx, cy):
            if angle_deg == 0: return x, y
            angle_rad = np.radians(angle_deg)
            nx = cx + (x - cx) * np.cos(angle_rad) - (y - cy) * np.sin(angle_rad)
            ny = cy + (x - cx) * np.sin(angle_rad) + (y - cy) * np.cos(angle_rad)
            return nx, ny

        def get_rotated_path(x1, y1, x2, y2, angle, cx, cy):
            if angle == 0:
                return f'M {x1} {y1} L {x2} {y1} L {x2} {y2} L {x1} {y2} Z'
            p1 = rotate_point(x1, y1, angle, cx, cy)
            p2 = rotate_point(x2, y1, angle, cx, cy)
            p3 = rotate_point(x2, y2, angle, cx, cy)
            p4 = rotate_point(x1, y2, angle, cx, cy)
            return f'M {p1[0]} {p1[1]} L {p2[0]} {p2[1]} L {p3[0]} {p3[1]} L {p4[0]} {p4[1]} Z'
            
        def get_rotated_and_translated_path(x1, y1, x2, y2, angle, cx_raw, cy_raw, cx_new, cy_new):
            dx = cx_new - cx_raw
            dy = cy_new - cy_raw
            p1 = rotate_point(x1, y1, angle, cx_raw, cy_raw)
            p2 = rotate_point(x2, y1, angle, cx_raw, cy_raw)
            p3 = rotate_point(x2, y2, angle, cx_raw, cy_raw)
            p4 = rotate_point(x1, y2, angle, cx_raw, cy_raw)
            return f'M {p1[0] + dx} {p1[1] + dy} L {p2[0] + dx} {p2[1] + dy} L {p3[0] + dx} {p3[1] + dy} L {p4[0] + dx} {p4[1] + dy} Z'
        
        # Calculate dynamic canvas size with a larger buffer
        text_buffer = 15 * text_scale + abs(text_y_off)
        max_dim = max(total_width + 20, barcode_height + text_buffer + 40)
        canvas_w = max_dim
        canvas_h = max_dim
        
        svg_header = f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        svg_header += f'<svg width="{canvas_w}mm" height="{canvas_h}mm" viewBox="{-canvas_w/2} {-canvas_h/2} {canvas_w} {canvas_h}" xmlns="http://www.w3.org/2000/svg">\n'
        
        svg_content = ""
        
        cx = 0
        cy = 0
        
        # Center the barcode vertically and horizontally before offsets
        x_base = cx - (total_width / 2)
        y_bars = cy - (barcode_height / 2)
        
        is_arte1 = (str(barcode_type).lower() == "gs1_128" and 5.8 <= float(barcode_height) <= 6.7)
        is_arte2 = (str(barcode_type).lower() == "gs1_128" and abs(float(barcode_height) - 5.1) < 0.1)
        
        # Calculate actual bounds of barcode bars to scale precisely
        min_bx = float('inf')
        max_bx = float('-inf')
        
        temp_x = x_base
        for bit in code:
            if bit == 'X':
                min_bx = min(min_bx, temp_x)
                max_bx = max(max_bx, temp_x + module_width)
            temp_x += module_width
            
        act_bw = max_bx - min_bx if min_bx != float('inf') else total_width
        
        if is_arte1:
            target_barcode_width = 39.62
            target_barcode_height = 5.15
            guard_width = 3.2
            guard_gap = 0.40
        elif is_arte2:
            # Physical compensation: 29.0 mm vector was measuring ~31.0 mm on the part.
            target_barcode_width = 26.1
            # Physical compensation: 9.0 mm overall width was measuring ~11.0 mm on the part.
            target_barcode_height = 4.17
            # Physical compensation: 3.0 mm vector guard was measuring ~4.0 mm on the part.
            guard_width = 2.25 # BARCODE GUARD TAMANHO
            guard_gap = 0.35
        else:
            target_barcode_width = act_bw
            target_barcode_height = barcode_height
            guard_width = 0.0
            guard_gap = 0.0

        inner_bar_width = max(target_barcode_width - 2 * (guard_width + guard_gap), target_barcode_width * 0.6)
        scale_x_bars = inner_bar_width / act_bw if act_bw > 0 else 1.0
        scale_y_bars = target_barcode_height / barcode_height if barcode_height else 1.0
        bx_center = (min_bx + max_bx) / 2 if min_bx != float('inf') else 0

        if guard_width > 0:
            gy1 = cy - target_barcode_height / 2
            gy2 = cy + target_barcode_height / 2
            gx1 = cx - target_barcode_width / 2
            gx2 = gx1 + guard_width
            d = get_rotated_path(gx1, gy1, gx2, gy2, barcode_rot, cx, cy)
            svg_content += f'  <path id="barcode_guard" d="{d}" fill="{barcode_color}" stroke="none" />\n'
            gx2 = cx + target_barcode_width / 2
            gx1 = gx2 - guard_width
            d = get_rotated_path(gx1, gy1, gx2, gy2, barcode_rot, cx, cy)
            svg_content += f'  <path id="barcode_guard" d="{d}" fill="{barcode_color}" stroke="none" />\n'

        bar_shrink_each_side = 0.05 if is_arte1 else (0.03 if is_arte2 else 0.0)
        run_start = None
        for idx, bit in enumerate(code + " "):
            if bit == 'X':
                if run_start is None:
                    run_start = idx
                continue
            if run_start is not None:
                run_end = idx
                x1_raw = (cx - (total_width / 2) + run_start * module_width) - bx_center
                x2_raw = (cx - (total_width / 2) + run_end * module_width) - bx_center
                y1_raw = y_bars - cy
                y2_raw = (y_bars + barcode_height) - cy

                x1_scaled = cx + x1_raw * scale_x_bars
                x2_scaled = cx + x2_raw * scale_x_bars
                y1_scaled = cy + y1_raw * scale_y_bars
                y2_scaled = cy + y2_raw * scale_y_bars

                run_width = x2_scaled - x1_scaled
                shrink = min(bar_shrink_each_side, max(0.0, run_width * 0.22))
                x1_scaled += shrink
                x2_scaled -= shrink

                if x2_scaled > x1_scaled:
                    d = get_rotated_path(x1_scaled, y1_scaled, x2_scaled, y2_scaled, barcode_rot, cx, cy)
                    svg_content += f'  <path id="barcode" d="{d}" fill="{barcode_color}" stroke="none" />\n'
                run_start = None

        # GENERATE TEXT AS PATHS
        try:
            # Resolve font path. The production sample uses an Arial-like outline, not a barcode text font.
            selected_font_path = self.font_path
            requested_font = font_name or "arial.ttf"
            if requested_font:
                if os.path.exists(requested_font):
                    selected_font_path = requested_font
                elif os.path.exists(requested_font + ".ttf"):
                    selected_font_path = requested_font + ".ttf"
                elif os.path.exists(os.path.join("C:/Windows/Fonts", requested_font + ".ttf")):
                    selected_font_path = os.path.join("C:/Windows/Fonts", requested_font + ".ttf")
                elif os.path.exists(os.path.join("C:/Windows/Fonts", requested_font)):
                    selected_font_path = os.path.join("C:/Windows/Fonts", requested_font)
                else:
                    win_fonts = "C:/Windows/Fonts"
                    if os.path.exists(win_fonts):
                        for fn in os.listdir(win_fonts):
                            if fn.lower() in (requested_font.lower(), requested_font.lower() + ".ttf", "arial.ttf"):
                                selected_font_path = os.path.join(win_fonts, fn)
                                break

            if selected_font_path and os.path.exists(selected_font_path):
                font_prop = FontProperties(fname=selected_font_path)
            else:
                font_prop = FontProperties(family="Arial")

            char_spacing_units = max(0.0, float(text_space) if text_space else 0.0) * 0.05
            cursor = 0.0
            char_paths = []
            for char in data:
                tp = TextPath((cursor, 0), char, size=1.0, prop=font_prop)
                char_paths.append(tp)
                try:
                    ext = tp.get_extents()
                    cursor = ext.x1 + char_spacing_units
                except Exception:
                    cursor += 0.6 + char_spacing_units

            all_points = []
            for tp in char_paths:
                for poly in tp.to_polygons():
                    if len(poly):
                        all_points.extend(poly)
            if not all_points:
                raise ValueError("No text outline points generated")

            xs = [p[0] for p in all_points]
            ys = [p[1] for p in all_points]
            min_rx, max_rx = min(xs), max(xs)
            min_ry, max_ry = min(ys), max(ys)
            act_w = max_rx - min_rx
            act_h = max_ry - min_ry

            if is_arte1:
                scale_x_text = 39.62 / act_w if act_w > 0 else 1.0
                scale_y_text = 5.15 / act_h if act_h > 0 else 1.0
                t_cy_offset = 5.15 / 2 + 1.70 + 5.15 / 2
            elif is_arte2:
                scale_x_text = 22.0 / act_w if act_w > 0 else 1.0
                scale_y_text = 2.94 / act_h if act_h > 0 else 1.0
                t_cy_offset = 4.17 / 2 + 0.25 + 2.94 / 2
            else:
                scale_x_text = 1.0
                scale_y_text = 1.0
                t_cy_offset = barcode_height / 2 + 5

            rx_center = (min_rx + max_rx) / 2 if act_w > 0 else 0
            ry_center = (min_ry + max_ry) / 2 if act_h > 0 else 0
            t_cx_raw = cx + text_x_off
            if text_pos == "bottom":
                t_cy_raw = cy + t_cy_offset + text_y_off
            else:
                t_cy_raw = cy - t_cy_offset + text_y_off
            t_cx, t_cy = rotate_point(t_cx_raw, t_cy_raw, barcode_rot, cx, cy)

            def transform_text_point(px, py):
                x_unrot = t_cx_raw + (px - rx_center) * scale_x_text
                y_unrot = t_cy_raw - (py - ry_center) * scale_y_text
                x_rot, y_rot = rotate_point(x_unrot, y_unrot, text_rot, t_cx_raw, t_cy_raw)
                return x_rot + (t_cx - t_cx_raw), y_rot + (t_cy - t_cy_raw)

            for tp in char_paths:
                char_parts = []
                for poly in tp.to_polygons():
                    if len(poly) < 2:
                        continue
                    x0, y0 = transform_text_point(poly[0][0], poly[0][1])
                    char_parts.append(f"M {x0} {y0}")
                    for px, py in poly[1:]:
                        x, y = transform_text_point(px, py)
                        char_parts.append(f"L {x} {y}")
                    char_parts.append("Z")
                if char_parts:
                    d = " ".join(char_parts)
                    svg_content += f'  <path id="text" d="{d}" fill="{text_color}" fill-rule="evenodd" stroke="{text_color}" />\n'
        except Exception as e:
            print(f"[DEBUG] Error converting text to paths: {e}")
            t_cy_offset_fallback = 6.5 / 2 + 3.0 + 6.0 / 2 if is_arte1 else (4.17 / 2 + 0.25 + 2.94 / 2 if is_arte2 else barcode_height / 2 + 10)
            text_y_raw = cy + t_cy_offset_fallback if text_pos == "bottom" else cy - t_cy_offset_fallback
            text_x, text_y = rotate_point(cx, text_y_raw, barcode_rot, cx, cy)
            text_id = "barcode" if group else "text"
            svg_content += f'  <text id="{text_id}" x="{text_x}" y="{text_y}" font-family="Arial" font-size="5" text-anchor="middle" fill="{text_color}">{data}</text>\n'
        
        svg_footer = '</svg>'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_header + svg_content + svg_footer)
        return output_path


    def generate_code128_vectors(self, data, barcode_height=20):
        EAN = barcode.get_barcode_class('code128')
        it = EAN(data)
        code = it.to_ascii()
        vectors = []
        module_width = 0.2
        x = 0
        for bit in code:
            if bit == 'X':
                vectors.append((x, 0, x, barcode_height))
            x += module_width
        return vectors, x

    def generate_code128_with_text(self, data, output_path, barcode_height=100, font_size=20, text_pos="bottom"):
        EAN = barcode.get_barcode_class('code128')
        it = EAN(data, writer=ImageWriter())
        options = {
            'module_height': barcode_height / 5.0,
            'write_text': False,
            'quiet_zone': 1.0
        }
        barcode_img = it.render(writer_options=options)
        bw, bh = barcode_img.size
        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except OSError:
            font = ImageFont.load_default()
            
        draw = ImageDraw.Draw(barcode_img)
        text_bbox = draw.textbbox((0, 0), data, font=font)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]
        
        padding = 10
        total_width = max(bw, tw + padding * 2)
        total_height = bh + th + padding * 2
        
        final_img = Image.new("RGB", (total_width, total_height), "white")
        bx = (total_width - bw) // 2
        tx = (total_width - tw) // 2
        
        if text_pos == "top":
            final_img.paste(barcode_img, (bx, th + padding))
            draw_final = ImageDraw.Draw(final_img)
            draw_final.text((tx, padding // 2), data, fill="black", font=font)
        else:
            final_img.paste(barcode_img, (bx, padding))
            draw_final = ImageDraw.Draw(final_img)
            draw_final.text((tx, bh + padding), data, fill="black", font=font)
            
        final_img.save(output_path)
        return output_path

if __name__ == "__main__":
    gen = BarcodeGenerator()
    gen.generate_code128_with_text("ABC-123456", "test_barcode.png", text_pos="bottom")
    print("Test barcode generated: test_barcode.png")
