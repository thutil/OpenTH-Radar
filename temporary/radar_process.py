import argparse
import subprocess
import shutil
import re
from pathlib import Path
import numpy as np
from PIL import Image
import rasterio

def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)

def which_or_die(bin_name):
    if shutil.which(bin_name) is None:
        raise RuntimeError(f"'{bin_name}' not found in PATH")
    return bin_name

def mask_rain_from_png(
    png_path, out_path,
    h_low=25, h_high=110,
    s_min=160, v_min=70,
    include_red=False,
    red_low=245, red_high=15,
    disk_shrink=0.96,
    left_crop_frac=0.18
):
    im = Image.open(png_path).convert("RGBA")
    w, h = im.size
    hsv = im.convert("RGB").convert("HSV")
    arr = np.array(hsv, dtype=np.uint8)
    H, S, V = arr[..., 0], arr[..., 1], arr[..., 2]
    gy = (H >= h_low) & (H <= h_high)
    sv = (S >= s_min) & (V >= v_min)
    if include_red:
        red = (H >= red_low) | (H <= red_high)
        hsv_mask = (gy | red) & sv
    else:
        hsv_mask = gy & sv
    cy, cx = h / 2.0, w / 2.0
    R = disk_shrink * min(w, h) * 0.5
    yy, xx = np.ogrid[:h, :w]
    circ = (xx - cx) ** 2 + (yy - cy) ** 2 <= R ** 2
    left_mask = np.ones((h, w), dtype=bool)
    cut = int(w * left_crop_frac)
    left_mask[:, :cut] = False
    keep = hsv_mask & circ & left_mask
    rgba = np.array(im, dtype=np.uint8)
    alpha = np.where(keep, 255, 0).astype(np.uint8)
    rgba[..., 3] = alpha
    rgb = rgba[..., :3]
    rgb[alpha == 0] = 0
    rgba[..., :3] = rgb
    Image.fromarray(rgba).convert("RGBA").save(out_path)
    return out_path

def copy_georef_from_template(template_tif, input_rgba_png, out_tif):
    with rasterio.open(template_tif) as tmpl:
        crs = tmpl.crs
        transform = tmpl.transform
    with Image.open(input_rgba_png).convert("RGBA") as im:
        w, h = im.size
        arr = np.array(im).transpose(2, 0, 1)
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "count": 4,
        "width": w,
        "height": h,
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
        "photometric": "RGB"
    }
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(arr)
    return out_tif

def extract_timestamp(filename):
    # ปรับ regex ตามรูปแบบไฟล์ของคุณ เช่น radar_YYYYMMDD_HHMM.png
    m = re.search(r'(\d{8}_\d{4})', filename)
    return m.group(1) if m else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template_dir", required=True, help="Directory containing template .tif files")
    ap.add_argument("--input_dir", required=True, help="Directory containing input .png files")
    ap.add_argument("--workdir", default="work")
    ap.add_argument("--h_low", type=int, default=25)
    ap.add_argument("--h_high", type=int, default=110)
    ap.add_argument("--s_min", type=int, default=160)
    ap.add_argument("--v_min", type=int, default=70)
    ap.add_argument("--include_red", action="store_true")
    ap.add_argument("--red_low", type=int, default=245)
    ap.add_argument("--red_high", type=int, default=15)
    ap.add_argument("--disk_shrink", type=float, default=0.96)
    ap.add_argument("--left_crop_frac", type=float, default=0.18)
    ap.add_argument("--zmin", type=int, default=5)
    ap.add_argument("--zmax", type=int, default=11)
    ap.add_argument("--skip_tiles", action="store_true")
    args = ap.parse_args()

    which_or_die("gdalwarp")
    which_or_die("gdal2tiles.py")
    which_or_die("gdal_translate")

    input_path = Path(args.input_dir)
    template_path = Path(args.template_dir)
    work_path = Path(args.workdir)
    work_path.mkdir(parents=True, exist_ok=True)

    png_files = list(input_path.glob("*.png"))
    if not png_files:
        print(f"No PNG files found in {args.input_dir}")
        return

    for png_file in png_files:
        timestamp = extract_timestamp(png_file.name)
        if not timestamp:
            print(f"Skip {png_file.name}: No timestamp found")
            continue

        base_name = png_file.stem
        template_file = template_path / f"{base_name}.tif"
        if not template_file.exists():
            print(f"Template not found for {png_file.name}: {template_file}")
            continue

        # สร้างโฟลเดอร์แยกตาม timestamp
        out_dir = work_path / timestamp
        out_dir.mkdir(parents=True, exist_ok=True)

        masked_png = out_dir / "rain_only.png"
        georef_tif = out_dir / "rain_only_georef.tif"
        webm_tif = out_dir / "rain_only_3857.tif"
        webm_rgba_tif = out_dir / "rain_only_3857_rgba.tif"
        tiles_dir = out_dir / "tiles"

        mask_rain_from_png(
            str(png_file), str(masked_png),
            h_low=args.h_low, h_high=args.h_high,
            s_min=args.s_min, v_min=args.v_min,
            include_red=args.include_red,
            red_low=args.red_low, red_high=args.red_high,
            disk_shrink=args.disk_shrink,
            left_crop_frac=args.left_crop_frac
        )
        print(f"[OK] Masked PNG → {masked_png}")

        copy_georef_from_template(str(template_file), str(masked_png), str(georef_tif))
        print(f"[OK] Georeferenced TIFF → {georef_tif}")

        if args.skip_tiles:
            continue

        run([
            "gdalwarp",
            "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
            "-overwrite",
            "-t_srs", "EPSG:3857",
            "-r", "near",
            "-srcalpha", "-dstalpha",
            "-of", "GTiff",
            "-co", "PHOTOMETRIC=RGB",
            "-co", "ALPHA=YES",
            str(georef_tif), str(webm_tif)
        ])

        run([
            "gdal_translate",
            "-b", "1", "-b", "2", "-b", "3", "-b", "4",
            str(webm_tif), str(webm_rgba_tif)
        ])

        tiles_dir.mkdir(exist_ok=True, parents=True)
        run([
            "gdal2tiles.py",
            "-z", f"{args.zmin}-{args.zmax}",
            "-r", "near",
            str(webm_rgba_tif),
            str(tiles_dir)
        ])
        print(f"[DONE] Tiles at: {tiles_dir}")

if __name__ == "__main__":
    main()
