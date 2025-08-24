import os
import cv2
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


def create_radar_heatmap(
    input_path="input.png",
    smooth_px=8,
    gamma=0.85,
    low_cut=0.15,
    feather=0.12,
    use_green_only=False
):
    if not os.path.exists(input_path):
        print(f"ไม่พบไฟล์ {input_path}")
        return

    image = cv2.imread(input_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w, _ = image_rgb.shape

    gray = cv2.cvtColor(image_rgb,
                        cv2.COLOR_RGB2GRAY
                        ).astype(np.float32) / 255.0

    if smooth_px > 0:
        gray_smooth = cv2.GaussianBlur(gray,
                                       ksize=(0, 0),
                                       sigmaX=smooth_px,
                                       sigmaY=smooth_px
                                       )
    else:
        gray_smooth = gray

    intensity = np.clip(gray_smooth, 0, 1) ** gamma

    alpha = np.clip((intensity - low_cut) / max(feather, 1e-6), 0.0, 1.0)

    if use_green_only:
        colors = [
            (0.0, 0.0, 0.0, 0.0),  # ใส (โปร่งใสสมบูรณ์)
            (0.85, 1.0, 0.85, 0.6),
            (0.5,  0.9, 0.5,  0.85),
            (0.0,  0.75, 0.0, 1.0)
        ]
        rain_cmap = LinearSegmentedColormap.from_list('rain_green_soft',
                                                      colors,
                                                      N=512)
    else:
        colors = [
            (0.0, 0.0, 0.0, 0.0),  # ใส (โปร่งใสสมบูรณ์)
            (0.80, 1.00, 0.80, 0.6),
            (0.00, 0.85, 0.00, 0.8),
            (0.90, 0.90, 0.00, 0.9),
            (1.00, 0.60, 0.10, 0.95),

        ]
        rain_cmap = LinearSegmentedColormap.from_list('rain_soft',
                                                      colors,
                                                      N=512)

    dpi = 100
    fig = plt.figure(figsize=(w/dpi, h/dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(intensity, cmap=rain_cmap, alpha=alpha, interpolation='bilinear')
    ax.axis('off')

    plt.savefig(input_path.replace(".png", "_smooth.png"),
                dpi=dpi,
                bbox_inches='tight',
                pad_inches=0,
                transparent=True)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input_path", required=True,
        help="Path to the input .png file"
    )
    args = ap.parse_args()

    create_radar_heatmap(
        input_path=args.input_path,
        smooth_px=8,
        gamma=0.80,
        low_cut=0.12,
        feather=0.10,
        use_green_only=False
    )
