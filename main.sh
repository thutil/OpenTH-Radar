#!/bin/bash
set -euo pipefail
# Remove virtual environment activation for Docker
# source .venv/bin/activate

baseURL="https://weather.tmd.go.th"

# See more URL: https://weather.tmd.go.th/xxx_HQ_edit2.php
filenames=(
    "chn/chn240_HQ_latest.png" 
    "phs/phs240_HQ_latest.png" 
    "cri/cri240_HQ_latest.png" 
    "skn/skn240_HQ_latest.png"
)

echo "==============================================="
echo "... Starting radar image download...   "
echo "==============================================="
for filename in "${filenames[@]}"; do
    printf "Downloading: %s/%s\n" "$baseURL" "$filename"
    outputFile="./$(basename "$filename")"
    curl -o "$outputFile" "$baseURL/$filename"
done


# หากสีแต่ละเรดาร์ไม่เหมือนกัน ปรับจูนได้จากค่า -zmin, -zmax, -s_min, -v_min ต้องทดลองเอาภาพไปลองปรับ HSV เอาเองว่าใช้เท่าไหร่
echo "==============================================="
echo "...... Starting radar image processing........   "
echo "==============================================="
python3 radar_process.py --template_tif ./geotif/chn240.tif --input_png chn240_HQ_latest.png \
  --workdir out/chn --zmin 5 --zmax 11 --h_low=5 --h_high=109 --s_min=196 --v_min=180 --skip_tiles

python3 radar_process.py --template_tif ./geotif/phs240.tif --input_png phs240_HQ_latest.png \
  --workdir out/phs --zmin 5 --zmax 11 --h_low=5 --h_high=109 --s_min=196 --v_min=180 --skip_tiles

python3 radar_process.py --template_tif ./geotif/cri240.tif --input_png cri240_HQ_latest.png \
  --workdir out/cri --zmin 5 --zmax 11 --h_low=5 --h_high=109 --s_min=116 --v_min=180 --skip_tiles

# python3 radar_process.py --template_tif ./geotif/skn240.tif --input_png skn240_HQ_latest.png \
#   --workdir out/skn --zmin 5 --zmax 11 --s_min=160 --v_min=150 --skip_tiles


echo "==============================================="
echo "..... Starting radar image to tile XYZ......   "
echo "==============================================="

# Clean previous output files
rm -f out/source_mosaic.vrt out/mosaic_3857.tif out/mosaic_3857_rgba.tif
rm -rf out/tiles

gdalbuildvrt -resolution highest \
  -hidenodata \
  -srcnodata "0 0 0 0" -vrtnodata "0 0 0 0" \
  out/source_mosaic.vrt \
  out/phs/rain_only_georef.tif \
  out/chn/rain_only_georef.tif \
  out/cri/rain_only_georef.tif 
#   out/skn/rain_only_georef.tif

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

echo "==============================================="
echo "....🌧️  Create tile with timestamp............."
echo "==============================================="
currentTime=$(date +%s)
roundedTime=$(( (currentTime / 600) * 600 ))
echo " 🌧️  Creating tiles for timestamp: $(date -d @$roundedTime +'%Y-%m-%d %H:%M:%S')"

if [ ! -d "./radar/$roundedTime" ]; then
    mkdir -p "./radar/$roundedTime"
fi

for dir in out/tiles/*; do
  if [ -d "$dir" ]; then
    mv "$dir" "./radar/$roundedTime/"
  fi
done

rm -rf out

