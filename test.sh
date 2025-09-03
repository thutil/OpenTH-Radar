# !/usr/bin/env bash
set -euo pipefail
# Base URL for radar images
baseURL="https://weather.tmd.go.th"

# List of filenames to download
filenames=("chn/chn240_HQ_latest.png" "phs/phs240_HQ_latest.png" "cri/cri240_HQ_latest.png")

for filename in "${filenames[@]}"; do
    printf "Downloading: %s/%s\n" "$baseURL" "$filename"
    outputFile="./$(basename "$filename")"
    curl -o "$outputFile" "$baseURL/$filename"
done


python3 test.py --template_tif chn240_HQ_latest_modified.tif --input_png chn240_HQ_latest.png \
  --workdir out/chn --zmin 5 --zmax 11 --s_min=160 --v_min=150 --skip_tiles

python3 test.py --template_tif phs240_HQ_latest_modified.tif --input_png phs240_HQ_latest.png \
  --workdir out/phs --zmin 5 --zmax 11 --s_min=160 --v_min=150 --skip_tiles

python3 test.py --template_tif cri240_HQ_latest_modified.tif --input_png cri240_HQ_latest.png \
  --workdir out/cri --zmin 5 --zmax 11 --s_min=116 --v_min=150 --skip_tiles

  for dir in chn phs cri; do
    (
      cd "out/$dir"
      python3 ../../heatmap.py --input_path "rain_only.png"
      if [ -f rain_only_smooth.png ]; then
        mv -f rain_only_smooth.png rain_only.png
      fi
    )
  done

gdalbuildvrt -resolution highest \
  -hidenodata \
  -srcnodata "0 0 0 0" -vrtnodata "0 0 0 0" \
  out/source_mosaic.vrt \
  out/phs/rain_only_georef.tif \
  out/chn/rain_only_georef.tif \
  out/cri/rain_only_georef.tif

gdal_edit -colorinterp_1 red -colorinterp_2 green -colorinterp_3 blue -colorinterp_4 alpha \
  out/source_mosaic.vrt || true

gdalwarp -multi -wo NUM_THREADS=ALL_CPUS \
  -t_srs EPSG:3857 -r near \
  -srcalpha -dstalpha \
  -of GTiff -co PHOTOMETRIC=RGB -co ALPHA=YES \
  out/source_mosaic.vrt out/mosaic_3857.tif

gdal_translate -b 1 -b 2 -b 3 -b 4 \
  out/mosaic_3857.tif out/mosaic_3857_rgba.tif

mkdir -p out/tiles
gdal2tiles.py -z 5-11 -r near out/mosaic_3857_rgba.tif out/tiles

echo "[DONE] Tiles at: out/tiles"