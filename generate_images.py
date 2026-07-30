"""Generate test annotation images with objects to label."""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = r"C:\Users\xinzi\Desktop\DeepTutor\data\test_images"
os.makedirs(OUT, exist_ok=True)

# Colors for different object types
COLORS = {
    "cat": "#E8A87C",
    "dog": "#95B8D1",
    "bird": "#F4A261",
    "car": "#E76F51",
    "plane": "#457B9D",
    "tree": "#2A9D8F",
    "building": "#6C757D",
}

# ── Generate images ──────────────────────────────────────────

def draw_object(draw, obj):
    x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
    color = obj.get("color", "#888")
    label = obj.get("label", "?")
    # Draw filled rect for the object
    draw.rectangle([x, y, x+w, y+h], fill=color, outline="#333", width=2)
    # Draw label text above
    draw.text((x+4, y-18), f"{label}", fill="#333")

    # Add face features for animals
    if label in ("cat", "dog"):
        # Eyes
        eye_size = min(w, h) // 8
        draw.ellipse([x + w//3 - eye_size, y + h//3 - eye_size, x + w//3 + eye_size, y + h//3 + eye_size], fill="#333")
        draw.ellipse([x + 2*w//3 - eye_size, y + h//3 - eye_size, x + 2*w//3 + eye_size, y + h//3 + eye_size], fill="#333")
        if label == "cat":
            # Cat ears
            draw.polygon([(x + w//4, y), (x + w//4 - 15, y - 25), (x + w//4 + 15, y)], fill=color, outline="#333")
            draw.polygon([(x + 3*w//4, y), (x + 3*w//4 - 15, y - 25), (x + 3*w//4 + 15, y)], fill=color, outline="#333")


# Image 1: Simple cats
img1 = Image.new("RGB", (800, 500), "#F5F0E8")
d1 = ImageDraw.Draw(img1)
d1.rectangle([0, 0, 799, 499], outline="#CCC", width=1)
d1.text((10, 5), "Task 1: Find the CATS", fill="#555")
objects1 = [
    {"x": 80, "y": 120, "w": 140, "h": 160, "label": "cat", "color": COLORS["cat"]},
    {"x": 320, "y": 280, "w": 120, "h": 100, "label": "dog", "color": COLORS["dog"]},
    {"x": 580, "y": 80, "w": 150, "h": 170, "label": "cat", "color": COLORS["cat"]},
    {"x": 200, "y": 380, "w": 60, "h": 60, "label": "bird", "color": COLORS["bird"]},
]
for obj in objects1:
    draw_object(d1, obj)
img1.save(os.path.join(OUT, "task1_find_cats.png"))

# Image 2: Cars on street
img2 = Image.new("RGB", (800, 500), "#D5E8D4")
d2 = ImageDraw.Draw(img2)
# Road
d2.rectangle([0, 300, 799, 500], fill="#B0B0B0")
d2.line([(0, 300), (799, 300)], fill="#999", width=3)
# Dashed line
for xx in range(0, 800, 60):
    d2.line([(xx, 400), (xx+30, 400)], fill="#FFF", width=3)
objects2 = [
    {"x": 60, "y": 330, "w": 140, "h": 70, "label": "car", "color": COLORS["car"]},
    {"x": 380, "y": 370, "w": 100, "h": 50, "label": "car", "color": COLORS["car"]},
    {"x": 620, "y": 310, "w": 130, "h": 65, "label": "car", "color": COLORS["car"]},
    {"x": 280, "y": 60, "w": 160, "h": 50, "label": "plane", "color": COLORS["plane"]},
    {"x": 150, "y": 150, "w": 50, "h": 70, "label": "tree", "color": COLORS["tree"]},
    {"x": 680, "y": 120, "w": 55, "h": 80, "label": "tree", "color": COLORS["tree"]},
]
for obj in objects2:
    draw_object(d2, obj)
img2.save(os.path.join(OUT, "task2_find_cars.png"))

# Image 3: Cats + Dogs (overlap)
img3 = Image.new("RGB", (800, 500), "#F0EDE4")
d3 = ImageDraw.Draw(img3)
d3.text((10, 5), "Task 3: Find ALL cats AND dogs", fill="#555")
objects3 = [
    {"x": 50, "y": 280, "w": 130, "h": 110, "label": "cat", "color": COLORS["cat"]},
    {"x": 150, "y": 290, "w": 120, "h": 95, "label": "dog", "color": COLORS["dog"]},
    {"x": 450, "y": 250, "w": 120, "h": 130, "label": "cat", "color": COLORS["cat"]},
    {"x": 520, "y": 260, "w": 115, "h": 105, "label": "dog", "color": COLORS["dog"]},
    {"x": 150, "y": 80, "w": 55, "h": 55, "label": "bird", "color": COLORS["bird"]},
    {"x": 680, "y": 100, "w": 62, "h": 62, "label": "bird", "color": COLORS["bird"]},
]
for obj in objects3:
    draw_object(d3, obj)
img3.save(os.path.join(OUT, "task3_cats_dogs.png"))

# Image 4: Buildings (easy)
img4 = Image.new("RGB", (800, 500), "#87CEEB")
d4 = ImageDraw.Draw(img4)
# Sky gradient
for i in range(500):
    color = (135 - i//10, 206 - i//10, 235 - i//10)
    d4.line([(0, i), (799, i)], fill=color)
# Ground
d4.rectangle([0, 350, 799, 500], fill="#7B904B")
objects4 = [
    {"x": 30, "y": 150, "w": 120, "h": 200, "label": "building", "color": COLORS["building"]},
    {"x": 180, "y": 100, "w": 100, "h": 250, "label": "building", "color": COLORS["building"]},
    {"x": 310, "y": 180, "w": 140, "h": 170, "label": "building", "color": COLORS["building"]},
    {"x": 500, "y": 130, "w": 110, "h": 220, "label": "building", "color": COLORS["building"]},
    {"x": 650, "y": 170, "w": 130, "h": 180, "label": "building", "color": COLORS["building"]},
]
for obj in objects4:
    draw_object(d4, obj)
img4.save(os.path.join(OUT, "task4_buildings.png"))

print(f"Generated {len(os.listdir(OUT))} images in {OUT}")
for f in sorted(os.listdir(OUT)):
    print(f"  {f}")
