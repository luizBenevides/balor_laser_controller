with open(r"C:\Users\paulo\.gemini\antigravity-cli\brain\13755bf6-cae3-487f-8f6e-8b3c1c035916\.system_generated\tasks\task-1295.log", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

light_strokes = 0
mark_hatches = 0
mark_strokes = 0

for line in lines:
    if "rendering lighting stroke" in line:
        light_strokes += 1
    if "rendering hatching" in line:
        mark_hatches += 1
    if "rendering marking stroke" in line:
        mark_strokes += 1

print("light_strokes (F1):", light_strokes)
print("mark_hatches (Mark fill):", mark_hatches)
print("mark_strokes (Mark stroke):", mark_strokes)
