import tkinter as tk
from svgpathtools import svg2paths2
import os

class PreviewManager:
    def __init__(self, canvas, gui_app):
        self.canvas = canvas
        self.gui = gui_app # Reference back to BalorStudioLite to access variables
        
        self.scale = 1.0
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        self.drag_data = {"x": 0, "y": 0, "item": None, "mode": None, "start_bbox": None}
        
        # Binds
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Dimension memory (mm)
        self.obj_dims = {"barcode": (0,0), "text": (0,0)}

    def clear(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self.canvas.create_line(w/2, 0, w/2, h, fill="#ccc", dash=(4,4))
        self.canvas.create_line(0, h/2, w, h/2, fill="#ccc", dash=(4,4))

    def load_svg(self, svg_path, preserve_transforms=True):
        if not svg_path or svg_path == "DUMMY" or not os.path.exists(svg_path):
            return

        self.clear()
        paths, attributes, svg_attributes = svg2paths2(svg_path)
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1: w, h = 600, 450
        cx, cy = w/2, h/2

        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        has_paths = False
        
        # Separate bounds for barcode and text to calculate mm
        bounds = {"barcode": [float('inf'), float('inf'), float('-inf'), float('-inf')], 
                  "text": [float('inf'), float('inf'), float('-inf'), float('-inf')]}    

        for path, attr in zip(paths, attributes):
            if len(path) == 0: continue
            has_paths = True
            bb = path.bbox()
            min_x = min(min_x, bb[0]); max_x = max(max_x, bb[1])
            min_y = min(min_y, bb[2]); max_y = max(max_y, bb[3])

            # Use path ID or parent group ID
            tag = attr.get('id', 'barcode') # Fallback is usually only for un-ID'd paths
            
            # Since composer might prefix or use raw 'text', 'barcode'
            if tag not in bounds:
                bounds[tag] = [float('inf'), float('inf'), float('-inf'), float('-inf')]

            bounds[tag][0] = min(bounds[tag][0], bb[0])
            bounds[tag][1] = min(bounds[tag][1], bb[2])
            bounds[tag][2] = max(bounds[tag][2], bb[1])
            bounds[tag][3] = max(bounds[tag][3], bb[3])

        if not has_paths: return

        svg_w = max_x - min_x
        svg_h = max_y - min_y

        # Calculate true dimensions in mm for labels
        self.obj_dims = {}
        for tag, b in bounds.items():
            if b[0] != float('inf'):
                self.obj_dims[tag] = (b[2] - b[0], b[3] - b[1])
            else:
                self.obj_dims[tag] = (0, 0)

        # Update GUI scale logic
        self.gui.svg_raw_width = svg_w
        self.gui.svg_raw_height = svg_h
        self.gui.svg_bounds = (min_x, max_x, min_y, max_y)
        self.gui._on_scale_change()

        # Fixed coordinate system: the composer always puts (0,0) at the center of the drawing area.
        # We calculate a reasonable initial scale if not set, but don't constantly shift the camera.
        margin = 40
        if not hasattr(self, 'base_scale') or self.gui.var_content_mode.get() != "svg":
            self.base_scale = min((w - margin) / (svg_w if svg_w>0 else 1), (h - margin) / (svg_h if svg_h>0 else 1))
            
        self.scale = self.base_scale * self.zoom

        try:
            gui_ox = float(self.gui.var_offset_x.get()) * self.scale
            gui_oy = float(self.gui.var_offset_y.get()) * self.scale
        except:
            gui_ox, gui_oy = 0, 0

        # Anchor camera directly to (0,0) of the SVG, projected onto cx,cy of the canvas
        offset_x = cx + self.pan_x + gui_ox
        offset_y = cy + self.pan_y + gui_oy

        for path, attr in zip(paths, attributes):
            # The composer preserves IDs on paths directly, but sometimes it might be on the parent
            # SVG attributes or in a group. SVGPathTools puts it in `attr['id']`.
            # If the path comes from our generator, it's explicitly 'barcode' or 'text'.
            # If it's a composed item, it has its explicit ID.
            obj_tag = attr.get('id', 'barcode') # Fallback
            
            # Look up assigned color in GUI
            color_name = self.gui.obj_colors.get(obj_tag, "Preto (#000000)")
            hex_color = self.gui.pens.get(color_name, {}).get("color_hex", "#007bff")
            
            for continuous_subpath in path.continuous_subpaths():
                pts = []
                for seg in continuous_subpath:
                    steps = 10
                    for i in range(steps + 1):
                        p = seg.point(i/steps)
                        pts.append((p.real * self.scale + offset_x, p.imag * self.scale + offset_y))
                if len(pts) > 1:
                    flat_pts = [item for sublist in pts for item in sublist]
                    self.canvas.create_line(flat_pts, fill=hex_color, width=1, tags=(obj_tag, "svg_obj"))

        self.draw_selection()
        if hasattr(self.gui, 'selected_obj') and self.gui.selected_obj.get():
            self.gui.sync_selected_object_controls()

    def on_mouse_wheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.zoom *= 0.9
        if event.num == 4 or event.delta > 0:
            self.zoom *= 1.1
        self.load_svg(self.gui.current_svg)

    def on_press(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item)
        print(f"[DEBUG][preview] on_press x={event.x} y={event.y} item={item} tags={tags}")
        
        # Reset drag start memory
        self.drag_data["start_x"] = event.x
        self.drag_data["start_y"] = event.y
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        
        if "handle" in tags:
            self.drag_data["mode"] = "resize"
            self.drag_data["handle"] = tags[1]
            sel = self.gui.selected_obj.get()
            if sel:
                self.drag_data["start_bbox"] = self.canvas.bbox(sel)
                # Store original scale/size values so math doesn't compound
                try:
                    self.drag_data["start_ws"] = float(self.gui.var_barcode_w_scale.get())
                    self.drag_data["start_h"] = float(self.gui.var_barcode_h.get())
                    self.drag_data["start_ts"] = float(self.gui.var_text_scale.get())
                    
                    for item in self.gui.custom_scene_items:
                        if item['id'] == sel:
                            self.drag_data["start_sx"] = item['sx']
                            self.drag_data["start_sy"] = item['sy']
                            break
                except: pass
        elif "svg_obj" in tags:
            # Extract the actual ID tag
            for t in tags:
                if t not in ("svg_obj", "current"):
                    self.gui.selected_obj.set(t)
                    self.gui.sync_selected_object_controls()
                    print(f"[DEBUG][preview] selected svg_obj={t} bbox={self.canvas.bbox(t)}")
                    break
            self.drag_data["mode"] = "move"
        else:
            self.gui.selected_obj.set("")
            self.drag_data["mode"] = None
            
        self.draw_selection()

    def on_drag(self, event):
        if not self.drag_data["mode"]: return
        
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        
        sel = self.gui.selected_obj.get()
        if not sel: return

        print(f"[DEBUG][preview] on_drag mode={self.drag_data['mode']} sel={sel} dx={dx} dy={dy}")
        
        if self.drag_data["mode"] == "move":
            mm_dx = dx / self.scale
            mm_dy = dy / self.scale
            if sel == "barcode":
                try:
                    self.gui.var_offset_x.set(f"{float(self.gui.var_offset_x.get()) + mm_dx:.2f}")
                    self.gui.var_offset_y.set(f"{float(self.gui.var_offset_y.get()) + mm_dy:.2f}")
                except: pass
            elif sel == "text":
                try:
                    self.gui.var_text_x_off.set(f"{float(self.gui.var_text_x_off.get()) + mm_dx:.2f}")
                    self.gui.var_text_y_off.set(f"{float(self.gui.var_text_y_off.get()) + mm_dy:.2f}")
                except: pass
            else:
                # Find custom object in scene
                for item in self.gui.custom_scene_items:
                    if item['id'] == sel:
                        item['ox'] += mm_dx
                        item['oy'] += mm_dy
                        max_z = max(([float(i.get('z', 0.0)) for i in self.gui.custom_scene_items] + [100.0]))
                        item['z'] = max_z + 1.0
                        self.gui.var_obj_off_x.set(f"{item['ox']:.4f}")
                        self.gui.var_obj_off_y.set(f"{item['oy']:.4f}")
                        print(f"[DEBUG][preview] move custom sel={sel} ox={item['ox']:.4f} oy={item['oy']:.4f} z={item['z']:.1f}")
                        break
            
            self.canvas.move(sel, dx, dy)
            self.canvas.tag_raise(sel)
            self.draw_selection()
            
        elif self.drag_data["mode"] == "resize":
            # True visual resizing
            bbox = self.canvas.bbox(sel)
            if not bbox: return
            
            old_w = bbox[2] - bbox[0]
            old_h = bbox[3] - bbox[1]
            
            if old_w <= 0 or old_h <= 0: return
            
            new_w = old_w + dx
            new_h = old_h + dy
            
            # Prevent inverting or collapsing
            if new_w < 5: new_w = 5
            if new_h < 5: new_h = 5
            
            # Recompute dx/dy based on clamped values
            actual_dx = new_w - old_w
            actual_dy = new_h - old_h
            
            fx = new_w / old_w
            fy = new_h / old_h
            
            # Apply visual scale incrementally
            self.canvas.scale(sel, bbox[0], bbox[1], fx, fy)
            
            # The object center shifted visually by actual_dx/2, actual_dy/2
            mm_dx = (actual_dx / 2.0) / self.scale
            mm_dy = (actual_dy / 2.0) / self.scale
            
            # Apply logical scale back to vars incrementally
            if sel == "barcode":
                try:
                    ws = float(self.gui.var_barcode_w_scale.get())
                    h = float(self.gui.var_barcode_h.get())
                    self.gui.var_barcode_w_scale.set(f"{ws * fx:.3f}")
                    self.gui.var_barcode_h.set(f"{h * fy:.2f}")
                    
                    ox = float(self.gui.var_offset_x.get())
                    oy = float(self.gui.var_offset_y.get())
                    self.gui.var_offset_x.set(f"{ox + mm_dx:.2f}")
                    self.gui.var_offset_y.set(f"{oy + mm_dy:.2f}")
                except: pass
            elif sel == "text":
                try:
                    ts = float(self.gui.var_text_scale.get())
                    scale_factor = (fx + fy) / 2.0
                    self.gui.var_text_scale.set(f"{ts * scale_factor:.3f}")
                    
                    tx = float(self.gui.var_text_x_off.get())
                    ty = float(self.gui.var_text_y_off.get())
                    self.gui.var_text_x_off.set(f"{tx + mm_dx:.2f}")
                    self.gui.var_text_y_off.set(f"{ty + mm_dy:.2f}")
                except: pass
            else:
                for item in self.gui.custom_scene_items:
                    if item['id'] == sel:
                        item['sx'] *= fx
                        item['sy'] *= fy
                        item['ox'] += mm_dx
                        item['oy'] += mm_dy
                        self.gui.var_obj_scale_x.set(f"{item['sx']:.4f}")
                        self.gui.var_obj_scale_y.set(f"{item['sy']:.4f}")
                        self.gui.var_obj_off_x.set(f"{item['ox']:.4f}")
                        self.gui.var_obj_off_y.set(f"{item['oy']:.4f}")
                        print(f"[DEBUG][preview] resize custom sel={sel} sx={item['sx']:.4f} sy={item['sy']:.4f} ox={item['ox']:.4f} oy={item['oy']:.4f} fx={fx:.4f} fy={fy:.4f}")
                        break

            self.draw_selection()

    def on_release(self, event):
        if self.drag_data["mode"]:
            sel = self.gui.selected_obj.get()
            print(f"[DEBUG][preview] on_release mode={self.drag_data['mode']} sel={sel}")
            if sel:
                self.gui.sync_selected_object_controls()
            # Regenerate SVG to lock in accurate vectors
            self.gui.update_content_mode()
        self.drag_data["mode"] = None

    def draw_selection(self):
        self.canvas.delete("sel_box")
        self.canvas.delete("handle")
        self.canvas.delete("dim_label")
        sel = self.gui.selected_obj.get()
        if not sel: return
        
        bbox = self.canvas.bbox(sel)
        if bbox:
            self.canvas.create_rectangle(bbox, outline="red", dash=(4,4), tags="sel_box")
            h_size = 5
            # Bottom-Right handle
            self.canvas.create_rectangle(
                bbox[2]-h_size, bbox[3]-h_size, bbox[2]+h_size, bbox[3]+h_size, 
                fill="red", tags=("handle", "br")
            )
            
            # Draw dimensions in MM
            w_mm, h_mm = self.obj_dims.get(sel, (0,0))
            
            # Apply global scale only (the SVG already has individual text/barcode scales baked in)
            try:
                sc = float(self.gui.var_scale.get())
            except:
                sc = 1.0

            w_mm = w_mm * sc
            h_mm = h_mm * sc

            dim_text = f"{w_mm:.1f}x{h_mm:.1f} mm"
            self.canvas.create_text(
                bbox[0], bbox[3] + 10,
                text=dim_text, fill="red", font=("Arial", 10, "bold"), anchor="w", tags="dim_label"
            )
            
            self.gui.lbl_filename.config(text=f"Selecionado: {'Barcode' if sel=='barcode' else 'Texto Serial' if sel=='text' else 'Arte'} ({dim_text})")
