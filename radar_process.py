import argparse, subprocess, shutil
import os
import glob
from pathlib import Path
from osgeo import gdal
import numpy as np
from PIL import Image


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template_dir", required=True, help="Directory containing template .tif files")
    ap.add_argument("--input_dir", required=True, help="Directory containing input .png files")
    ap.add_argument("--workdir", default="work")

    # masking params
    ap.add_argument("--h_low", type=int, default=25)
    ap.add_argument("--h_high", type=int, default=110)
    ap.add_argument("--s_min", type=int, default=160)
    ap.add_argument("--v_min", type=int, default=70)
    ap.add_argument("--include_red", action="store_true")
    ap.add_argument("--red_low", type=int, default=245)
    ap.add_argument("--red_high", type=int, default=15)
    ap.add_argument("--disk_shrink", type=float, default=0.96)
    ap.add_argument("--left_crop_frac", type=float, default=0.18)

    # tiling params
    ap.add_argument("--zmin", type=int, default=5)
    ap.add_argument("--zmax", type=int, default=11)
    ap.add_argument("--skip_tiles", action="store_true")

    args = ap.parse_args()
    print("Arguments:", args)

    # Create work directory
    work_path = Path(args.workdir)
    work_path.mkdir(parents=True, exist_ok=True)

    # Find all PNG files in input directory
    input_path = Path(args.input_dir)
    png_files = list(input_path.glob("*.png"))
    
    if not png_files:
        print(f"No PNG files found in {args.input_dir}")
        return

    print(f"Found {len(png_files)} PNG files to process")

    # Process each PNG file
    for png_file in png_files:
        print(f"\nProcessing: {png_file.name}")
        
        # Get corresponding template file
        base_name = png_file.stem  # filename without extension
        template_file = Path(args.template_dir) / f"{base_name}_modified.tif"
        
        if not template_file.exists():
            print(f"Warning: Template file not found for {png_file.name}: {template_file}")
            continue
            
        print(f"Using template: {template_file}")
        
        # Create output paths directly in work directory (no subdirectories)
        masked_png = work_path / f"{base_name}_rain_only.png"
        georef_tif = work_path / f"{base_name}_rain_only_georef.tif"
        webm_tif = work_path / f"{base_name}_rain_only_3857.tif"
        webm_rgba_tif = work_path / f"{base_name}_rain_only_3857_rgba.tif"
        tiles_dir = work_path / f"{base_name}_tiles"

        # Process the PNG file
        mask_rain_from_png(
            str(png_file), str(masked_png),
            h_low=args.h_low, h_high=args.h_high,
            s_min=args.s_min, v_min=args.v_min,
            include_red=args.include_red,
            red_low=args.red_low, red_high=args.red_high,
            disk_shrink=args.disk_shrink,
            left_crop_frac=args.left_crop_frac
        )
        print(f"Created Mask PNG → {masked_png}")
        
        # Georeference the masked PNG using the template
        georeference_png(str(masked_png), str(template_file), str(georef_tif))
        print(f"Created Georeferenced TIF → {georef_tif}")


def georeference_png(masked_png_path, template_tif_path, output_tif_path):
    """Georeference the masked PNG using template TIF as reference"""
    
    # Open template to get geospatial info
    template_ds = gdal.Open(template_tif_path)
    if template_ds is None:
        raise ValueError(f"Could not open template file: {template_tif_path}")
    
    # Get geotransform and projection from template
    geotransform = template_ds.GetGeoTransform()
    projection = template_ds.GetProjection()
    
    # Open the masked PNG
    png_image = Image.open(masked_png_path)
    png_array = np.array(png_image)
    
    # Create output GeoTIFF
    driver = gdal.GetDriverByName('GTiff')
    
    if len(png_array.shape) == 3:  # RGB or RGBA
        height, width, bands = png_array.shape
    else:  # Grayscale
        height, width = png_array.shape
        bands = 1
    
    # Create the output dataset
    out_ds = driver.Create(output_tif_path, width, height, bands, gdal.GDT_Byte)
    
    # Set geospatial information
    out_ds.SetGeoTransform(geotransform)
    out_ds.SetProjection(projection)
    
    # Write the data
    if bands == 1:
        out_ds.GetRasterBand(1).WriteArray(png_array)
    else:
        for i in range(bands):
            out_ds.GetRasterBand(i + 1).WriteArray(png_array[:, :, i])
    
    # Cleanup
    out_ds = None
    template_ds = None

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


if __name__ == "__main__":
    main()
