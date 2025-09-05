import argparse
import subprocess
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
import rasterio
from matplotlib.colors import LinearSegmentedColormap
import cv2
import matplotlib.pyplot as plt


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def which_or_die(bin_name):
    if shutil.which(bin_name) is None:
        raise RuntimeError(f"'{bin_name}' not found in PATH")
    return bin_name


def mask_rain_from_png(
    png_path,
    out_path,
    h_low=25,
    h_high=110,
    s_min=160,
    v_min=70,
    include_red=False,
    red_low=245,
    red_high=15,
    disk_shrink=0.96,
    left_crop_frac=0.18,
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
    circ = (xx - cx) ** 2 + (yy - cy) ** 2 <= R**2

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


def create_radar_heatmap(
    input_path,
    smooth_px=8,
    gamma=0.85,
    low_cut=0.15,
    feather=0.12,
    use_green_only=False,
):

    image = cv2.imread(str(input_path))
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w, _ = image_rgb.shape

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0

    if smooth_px > 0:
        gray_smooth = cv2.GaussianBlur(
            gray, ksize=(0, 0), sigmaX=smooth_px, sigmaY=smooth_px
        )
    else:
        gray_smooth = gray

    intensity = np.clip(gray_smooth, 0, 1) ** gamma

    alpha = np.clip((intensity - low_cut) / max(feather, 1e-6), 0.0, 1.0)

    if use_green_only:
        colors = [
            (0.0, 0.0, 0.0, 0.0),
            (0.85, 1.0, 0.85, 0.6),
            (0.5, 0.9, 0.5, 0.85),
            (0.0, 0.75, 0.0, 1.0),
        ]
        rain_cmap = LinearSegmentedColormap.from_list("rain_green_soft", colors, N=512)
    else:
        colors = [
            (0.0, 0.0, 0.0, 0.0),
            (0.80, 1.00, 0.80, 0.6),
            (0.00, 0.85, 0.00, 0.8),
            (0.90, 0.90, 0.00, 0.9),
            (1.00, 0.60, 0.10, 0.95),
        ]
        rain_cmap = LinearSegmentedColormap.from_list("rain_soft", colors, N=512)

    dpi = 100
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(intensity, cmap=rain_cmap, alpha=alpha, interpolation="bilinear")
    ax.axis("off")

    plt.savefig(
        str(input_path).replace(".png", "_smooth.png"),
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0,
        transparent=True,
    )
    plt.close(fig)


def fix_radar_gaps(
    img_bgra: np.ndarray,
    nonblack_threshold: int = 10,
    neighbor_kernel_size: int = 6,
    min_neighbors: int = 6,
    disk_dilate: int = 31,
    inpaint_radius: int = 3,
    feather_px: int = 1,
    max_alpha: int = 255, 
    antialias_sigma: float = 0.8, 
) -> np.ndarray:

    if img_bgra.ndim == 3 and img_bgra.shape[2] == 4:
        bgr = img_bgra[:, :, :3].copy()
        _ = img_bgra[:, :, 3]
    else:
        bgr = img_bgra.copy()

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    nonblack = (gray > nonblack_threshold).astype(np.uint8)

    k = np.ones((neighbor_kernel_size, neighbor_kernel_size), np.uint8)
    neighbor_count = cv2.filter2D(nonblack, -1, k, borderType=cv2.BORDER_DEFAULT)
    is_black = (nonblack == 0).astype(np.uint8)
    gap_mask = ((neighbor_count >= min_neighbors) & (is_black == 1)).astype(
        np.uint8
    ) * 255

    disk_area = cv2.dilate(
        nonblack,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (disk_dilate, disk_dilate)),
        iterations=1,
    )
    gap_mask = cv2.bitwise_and(gap_mask, (disk_area * 255).astype(np.uint8))

    repaired = cv2.inpaint(
        bgr, gap_mask, inpaintRadius=inpaint_radius, flags=cv2.INPAINT_TELEA
    )

    core = cv2.morphologyEx(
        nonblack,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    core = cv2.morphologyEx(
        core,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )

    dist_in = cv2.distanceTransform(core, cv2.DIST_L2, 5).astype(np.float32)

    if feather_px <= 0:
        ramp = core.astype(np.float32)
    else:
        ramp = np.clip(dist_in / float(feather_px), 0.0, 1.0)
    a = (ramp * float(max_alpha)).astype(np.uint8)
    if antialias_sigma > 0:
        a = cv2.GaussianBlur(a, ksize=(0, 0), sigmaX=antialias_sigma)

    out = np.dstack([repaired, a])
    return out


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
        "photometric": "RGB",
    }
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(arr)
    return out_tif


# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template_tif", required=True)
    ap.add_argument("--input_png", required=True)
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

    # tiling params
    ap.add_argument("--zmin", type=int, default=5)
    ap.add_argument("--zmax", type=int, default=11)
    ap.add_argument("--skip_tiles", action="store_true")

    args = ap.parse_args()

    which_or_die("gdalwarp")
    which_or_die("gdal2tiles.py")
    which_or_die("gdal_translate")

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)

    masked_png = work / "rain_only.png"
    masked_heatmap_png = work / "rain_only_smooth.png"
    georef_tif = work / "rain_only_georef.tif"
    webm_tif = work / "rain_only_3857.tif"
    webm_rgba_tif = work / "rain_only_3857_rgba.tif"
    tiles_dir = work / "tiles"

    # 1) Mask
    mask_rain_from_png(
        args.input_png,
        str(masked_png),
        h_low=args.h_low,
        h_high=args.h_high,
        s_min=args.s_min,
        v_min=args.v_min,
        include_red=args.include_red,
        red_low=args.red_low,
        red_high=args.red_high,
        disk_shrink=args.disk_shrink,
        left_crop_frac=args.left_crop_frac,
    )
    print(f"[OK] Masked PNG → {masked_png}")

    # create_radar_heatmap(
    #     input_path=masked_png,
    #     smooth_px=8,
    #     gamma=0.85,
    #     low_cut=0.15,
    #     feather=0.12,
    #     use_green_only=False,
    # )

    out = fix_radar_gaps(
        img_bgra=cv2.imread(str(masked_png), cv2.IMREAD_UNCHANGED),
        nonblack_threshold=5,
        neighbor_kernel_size=3,
        min_neighbors=3,
        disk_dilate=31,
        inpaint_radius=3,
    )

    cv2.imwrite(str(masked_heatmap_png), out)

    copy_georef_from_template(
        args.template_tif, str(masked_heatmap_png), str(georef_tif)
    )
    # print(f"[OK] Georeferenced TIFF → {georef_tif}")

    # if args.skip_tiles:
    #     return

    # run(
    #     [
    #         "gdalwarp",
    #         "-multi",
    #         "-wo",
    #         "NUM_THREADS=ALL_CPUS",
    #         "-overwrite",
    #         "-t_srs",
    #         "EPSG:3857",
    #         "-r",
    #         "near",
    #         "-srcalpha",
    #         "-dstalpha",
    #         "-of",
    #         "GTiff",
    #         "-co",
    #         "PHOTOMETRIC=RGB",
    #         "-co",
    #         "ALPHA=YES",
    #         str(georef_tif),
    #         str(webm_tif),
    #     ]
    # )

    # run(
    #     [
    #         "gdal_translate",
    #         "-b",
    #         "1",
    #         "-b",
    #         "2",
    #         "-b",
    #         "3",
    #         "-b",
    #         "4",
    #         str(webm_tif),
    #         str(webm_rgba_tif),
    #     ]
    # )

    # tiles_dir.mkdir(exist_ok=True, parents=True)
    # run(
    #     [
    #         "gdal2tiles.py",
    #         "-z",
    #         f"{args.zmin}-{args.zmax}",
    #         "-r",
    #         "near",
    #         str(webm_rgba_tif),
    #         str(tiles_dir),
    #     ]
    # )
    # print(f"[DONE] Tiles at: {tiles_dir}")


if __name__ == "__main__":
    main()
