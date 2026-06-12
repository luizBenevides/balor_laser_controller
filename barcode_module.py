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
                             barcode_rot=0, text_rot=0, barcode_color="#000000", text_color="#000000"):
        """
        Generates a Code 128 barcode as an SVG file with vector paths for both bars AND text,
        supporting individual scaling, offsets, rotation, and colors.
        """
        EAN = barcode.get_barcode_class('code128')
        it = EAN(data)
        code = it.to_ascii() # Binary string ('X' for bar, ' ' for space)
        
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
        
        for bit in code:
            if bit == 'X':
                d = get_rotated_path(x_base, y_bars, x_base+module_width, y_bars + barcode_height, barcode_rot, cx, cy)
                svg_content += f'  <path id="barcode" d="{d}" fill="{barcode_color}" />\n'
            x_base += module_width
            
        # GENERATE TEXT AS PATHS
        try:
            font_size = int(24 * text_scale)
            if font_size < 1: font_size = 1
            try:
                font = ImageFont.truetype(self.font_path, font_size)
            except OSError:
                font = ImageFont.load_default()
            
            bbox = font.getbbox(data)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            img = Image.new("1", (tw + 2, th + 2), color=1)
            draw = ImageDraw.Draw(img)
            draw.text((1 - bbox[0], 1 - bbox[1]), data, font=font, fill=0)
            ary = np.array(img)
            
            text_x_res = 0.1
            text_y_res = 0.1
            
            text_total_w = (tw + 2) * text_x_res
            t_cx = cx + text_x_off
            
            if text_pos == "bottom":
                t_cy = cy + (barcode_height/2) + 5 + text_y_off
            else:
                t_cy = cy - (barcode_height/2) - 5 + text_y_off
            
            start_x = t_cx - (text_total_w / 2)
            start_y = t_cy - ((th + 2) * text_y_res / 2)
            
            for iy in range(ary.shape[0]):
                ix = 0
                while ix < ary.shape[1]:
                    if ary[iy, ix] == 0:
                        run = 1
                        while ix + run < ary.shape[1] and ary[iy, ix + run] == 0:
                            run += 1
                        
                        x1 = start_x + ix * text_x_res
                        x2 = start_x + (ix + run) * text_x_res
                        y1 = start_y + iy * text_y_res
                        y2 = start_y + (iy + 1) * text_y_res
                        d = get_rotated_path(x1, y1, x2, y2, text_rot, t_cx, t_cy)
                        svg_content += f'  <path id="text" d="{d}" fill="{text_color}" />\n'
                        ix += run
                    else:
                        ix += 1
        except Exception as e:
            print(f"[DEBUG] Error converting text to paths: {e}")
            text_y = cy + barcode_height/2 + 10 if text_pos == "bottom" else cy - barcode_height/2 - 5
            svg_content += f'  <text id="text" x="{cx}" y="{text_y}" font-family="Arial" font-size="5" text-anchor="middle" fill="{text_color}">{data}</text>\n'
        
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