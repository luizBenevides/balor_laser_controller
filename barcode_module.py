import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import os
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
        
        is_arte1 = (str(barcode_type).lower() == "gs1_128" and ("Barcode Font34" in str(font_name)) and abs(float(barcode_height) - 6.5) < 0.1)
        is_arte2 = (str(barcode_type).lower() == "gs1_128" and ("Barcode Font34" in str(font_name)) and abs(float(barcode_height) - 5.1) < 0.1)
        
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
            scale_x_bars = 39.62 / act_bw
            scale_y_bars = 6.5 / barcode_height
        elif is_arte2:
            scale_x_bars = 29.0 / act_bw
            scale_y_bars = 5.1 / barcode_height
        else:
            scale_x_bars = 1.0
            scale_y_bars = 1.0
        
        bx_center = (min_bx + max_bx) / 2 if min_bx != float('inf') else 0
        for bit in code:
            if bit == 'X':
                x1_raw = x_base - bx_center
                x2_raw = (x_base + module_width) - bx_center
                y1_raw = y_bars - cy
                y2_raw = (y_bars + barcode_height) - cy
                
                x1_scaled = cx + x1_raw * scale_x_bars
                x2_scaled = cx + x2_raw * scale_x_bars
                y1_scaled = cy + y1_raw * scale_y_bars
                y2_scaled = cy + y2_raw * scale_y_bars
                
                d = get_rotated_path(x1_scaled, y1_scaled, x2_scaled, y2_scaled, barcode_rot, cx, cy)
                svg_content += f'  <path id="barcode" d="{d}" fill="{barcode_color}" />\n'
            x_base += module_width
            
        # GENERATE TEXT AS PATHS
        try:
            # Resolve font path
            selected_font_path = self.font_path
            if font_name:
                if os.path.exists(font_name):
                    selected_font_path = font_name
                elif os.path.exists(font_name + ".ttf"):
                    selected_font_path = font_name + ".ttf"
                elif os.path.exists(os.path.join("C:/Windows/Fonts", font_name + ".ttf")):
                    selected_font_path = os.path.join("C:/Windows/Fonts", font_name + ".ttf")
                elif os.path.exists(os.path.join("C:/Windows/Fonts", font_name)):
                    selected_font_path = os.path.join("C:/Windows/Fonts", font_name)
                else:
                    win_fonts = "C:/Windows/Fonts"
                    if os.path.exists(win_fonts):
                        for fn in os.listdir(win_fonts):
                            if fn.lower() == font_name.lower() or fn.lower() == (font_name.lower() + ".ttf"):
                                selected_font_path = os.path.join(win_fonts, fn)
                                break

            font_size = int(24 * text_scale)
            if font_size < 1: font_size = 1
            try:
                font = ImageFont.truetype(selected_font_path, font_size)
            except OSError:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except OSError:
                    font = ImageFont.load_default()
            
            char_spacing = float(text_space) if text_space else 0.0
            
            if char_spacing > 0:
                # Calculate total width with custom spacing
                tw = 0
                th = 0
                char_widths = []
                for char in data:
                    c_bbox = font.getbbox(char)
                    c_w = c_bbox[2] - c_bbox[0]
                    c_h = c_bbox[3] - c_bbox[1]
                    char_widths.append(c_w)
                    tw += c_w
                    th = max(th, c_h)
                
                # Add spacing dynamically
                space_pixels = int(char_spacing * font_size / 2.0)
                tw += space_pixels * (len(data) - 1)
                
                img = Image.new("1", (tw + 10, th + 10), color=1)
                draw = ImageDraw.Draw(img)
                
                char_x = 5.0
                y_pos = 5.0
                for idx, char in enumerate(data):
                    c_bbox = font.getbbox(char)
                    draw.text((char_x - c_bbox[0], y_pos - c_bbox[1]), char, font=font, fill=0)
                    char_x += char_widths[idx] + space_pixels
            else:
                bbox = font.getbbox(data)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                img = Image.new("1", (tw + 2, th + 2), color=1)
                draw = ImageDraw.Draw(img)
                draw.text((1 - bbox[0], 1 - bbox[1]), data, font=font, fill=0)
                
            ary = np.array(img)
            
            text_x_res = 0.1
            text_y_res = 0.1
            
            text_total_w = (tw + 2) * text_x_res
            text_total_h = (th + 2) * text_y_res
            
            # Pass 1: Collect raw relative rectangles and compute actual text boundaries
            start_x_rel = - (text_total_w / 2)
            start_y_rel = - (text_total_h / 2)
            
            raw_rects = []
            min_rx, min_ry = float('inf'), float('inf')
            max_rx, max_ry = float('-inf'), float('-inf')
            
            for iy in range(ary.shape[0]):
                ix = 0
                while ix < ary.shape[1]:
                    if ary[iy, ix] == 0:
                        run = 1
                        while ix + run < ary.shape[1] and ary[iy, ix + run] == 0:
                            run += 1
                        
                        rx1 = start_x_rel + ix * text_x_res
                        rx2 = start_x_rel + (ix + run) * text_x_res
                        ry1 = start_y_rel + iy * text_y_res
                        ry2 = start_y_rel + (iy + 1) * text_y_res
                        
                        min_rx = min(min_rx, rx1)
                        max_rx = max(max_rx, rx2)
                        min_ry = min(min_ry, ry1)
                        max_ry = max(max_ry, ry2)
                        
                        raw_rects.append((rx1, ry1, rx2, ry2))
                        ix += run
                    else:
                        ix += 1
                        
            act_w = max_rx - min_rx if min_rx != float('inf') else text_total_w
            act_h = max_ry - min_ry if min_ry != float('inf') else text_total_h
            
            if is_arte1:
                scale_x_text = 39.62 / act_w if act_w > 0 else 1.0
                scale_y_text = 6.0 / act_h if act_h > 0 else 1.0
                t_cy_offset = 6.5 / 2 + 3.0 + 6.0 / 2 # 9.25 mm
                rx_center = (min_rx + max_rx) / 2 if min_rx != float('inf') else 0
                ry_center = (min_ry + max_ry) / 2 if min_ry != float('inf') else 0
            elif is_arte2:
                scale_x_text = 22.0 / act_w if act_w > 0 else 1.0
                scale_y_text = 3.6 / act_h if act_h > 0 else 1.0
                t_cy_offset = 5.1 / 2 + 0.3 + 3.6 / 2 # 4.65 mm
                rx_center = (min_rx + max_rx) / 2 if min_rx != float('inf') else 0
                ry_center = (min_ry + max_ry) / 2 if min_ry != float('inf') else 0
            else:
                scale_x_text = 1.0
                scale_y_text = 1.0
                t_cy_offset = barcode_height / 2 + 5
                rx_center = 0
                ry_center = 0
                
            t_cx_raw = cx + text_x_off
            if text_pos == "bottom":
                t_cy_raw = cy + t_cy_offset + text_y_off
            else:
                t_cy_raw = cy - t_cy_offset + text_y_off
            
            # Rotate text center point around the barcode center by barcode_rot
            t_cx, t_cy = rotate_point(t_cx_raw, t_cy_raw, barcode_rot, cx, cy)
            
            def line_path_from_rect(x1, y1, x2, y2):
                yc = (y1 + y2) / 2.0
                p1 = rotate_point(x1, yc, text_rot, t_cx_raw, t_cy_raw)
                p2 = rotate_point(x2, yc, text_rot, t_cx_raw, t_cy_raw)
                dx = t_cx - t_cx_raw
                dy = t_cy - t_cy_raw
                return f"M {p1[0] + dx} {p1[1] + dy} L {p2[0] + dx} {p2[1] + dy}"

            # Pass 2: Output rotated/scaled/translated paths
            for rx1, ry1, rx2, ry2 in raw_rects:
                # Scale relative to actual bounding box center to avoid offset distortion
                x1_scaled = (rx1 - rx_center) * scale_x_text
                x2_scaled = (rx2 - rx_center) * scale_x_text
                y1_scaled = (ry1 - ry_center) * scale_y_text
                y2_scaled = (ry2 - ry_center) * scale_y_text
                
                # Translate to raw unrotated center
                x1_unrot = t_cx_raw + x1_scaled
                x2_unrot = t_cx_raw + x2_scaled
                y1_unrot = t_cy_raw + y1_scaled
                y2_unrot = t_cy_raw + y2_scaled
                
                d = line_path_from_rect(x1_unrot, y1_unrot, x2_unrot, y2_unrot)
                svg_content += f'  <path id="text" d="{d}" stroke="{text_color}" fill="none" />\n'
        except Exception as e:
            print(f"[DEBUG] Error converting text to paths: {e}")
            t_cy_offset_fallback = 6.5 / 2 + 3.0 + 6.0 / 2 if is_arte1 else (5.1 / 2 + 0.3 + 3.6 / 2 if is_arte2 else barcode_height / 2 + 10)
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
