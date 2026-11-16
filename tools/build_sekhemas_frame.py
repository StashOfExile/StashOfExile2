"""Builds the trial map's frame parts in soe2/sekhemas.json (the Trial of the Sekhemas helper's map check) from a
screenshot of the open trial map (any resolution; the map window in the middle, as the game shows it).

  python3.12 tools/build_sekhemas_frame.py tests/fixtures/sekhemas_map_a.jpg

Each part is a piece of the map window's frame that is the same on every floor - the scroll's four roller knobs,
the title bar's two ends and its info / close buttons, the arch button - kept as a small gray picture (its spot in
parts of the game's height, x from the middle). Run it again if the game redraws the map window."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# where each part is on a 2560 x 1440 shot (real pixels; the map window's middle at x 1280)
PARTS_1440 = {"knob_top_left": (555, 165, 640, 205), "knob_top_right": (1920, 165, 2005, 205),
              "info_button": (790, 155, 835, 200), "close_button": (1740, 158, 1780, 198),
              "title_left": (840, 152, 1100, 196), "title_right": (1460, 152, 1720, 196),
              "arch_button": (671, 1097, 722, 1152),
              "knob_bottom_left": (548, 1102, 647, 1142), "knob_bottom_right": (1913, 1102, 2012, 1142)}


def rel(box, w=2560, h=1440):
    cx = w / 2.0
    return ((box[0] - cx) / h, box[1] / h, (box[2] - cx) / h, box[3] / h)


def main(path):
    from PIL import Image
    from soe2 import sekhemas as SK
    img = Image.open(path).convert("RGB")
    frame = {"made_from": os.path.basename(path), "scale_h": SK.SCALE_H,
             "parts": {k: SK.make_part(img, rel(b)) for k, b in PARTS_1440.items()}}
    dst = os.path.join(ROOT, "soe2", "sekhemas.json")
    with open(dst, encoding="utf-8") as f:
        d = json.load(f)
    d["frame"] = frame
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
        f.write("\n")
    SK._DATA.clear()
    got = SK.map_check(img)
    print(f"{len(frame['parts'])} parts written to {os.path.relpath(dst, ROOT)}; the shot itself: {got['parts']} of "
          f"{got['of']} there -> {'open' if got['open'] else 'NOT open'}")
    return 0 if got["open"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
