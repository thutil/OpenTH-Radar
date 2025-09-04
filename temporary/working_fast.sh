#!/bin/bash

# Fast parallel version of working.sh
# This script processes multiple timestamps in parallel for better performance

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source .venv/bin/activate

# Function to process a single timestamp directory
process_timestamp() {
    local timestamp_dir="$1"
    local timestamp=$(basename "$timestamp_dir")
    
    echo "🔄 [$(date '+%H:%M:%S')] Processing timestamp: $timestamp"
    
    # Step 1: Process radar images
    echo "  📊 Processing radar images for $timestamp..."
    python3 radar_process.py \
        --input_dir "$timestamp_dir" \
        --workdir "./radar_process/$timestamp" \
        --s_min 200 \
        --v_min 70 \
        --disk_shrink 0.96 \
        --left_crop_frac 0.18
    
    # Step 2: Color tuning
    echo "  🎨 Color tuning for $timestamp..."
    for img in "./radar_process/$timestamp"*.png; do
        if [ -f "$img" ]; then
            python3 heatmap.py --input_path "$img"
        fi
    done
    
    # Step 3: Create tiles
    echo "  🗺️  Creating tiles for $timestamp..."
    create_tiles_for_timestamp "$timestamp"
    
    echo "✅ [$(date '+%H:%M:%S')] Completed timestamp: $timestamp"
}

# Function to create tiles for a specific timestamp
create_tiles_for_timestamp() {
    local timestamp="$1"
    local timestamp_dir="radar_process/$timestamp"
    local output_dir="out/$timestamp"
    
    mkdir -p "$output_dir"/{phs,chn,cri}
    
    # Check if we have processed images
    local phs_img="$timestamp_dir/phs240_HQ_latest_rain_only_smooth.png"
    local chn_img="$timestamp_dir/chn240_HQ_latest_rain_only_smooth.png"
    local cri_img="$timestamp_dir/cri240_HQ_latest_rain_only_smooth.png"
    
    # Skip if no processed images found
    if [ ! -f "$phs_img" ] && [ ! -f "$chn_img" ] && [ ! -f "$cri_img" ]; then
        echo "    ⚠️  No processed images found for $timestamp, skipping tiles..."
        return
    fi
    
    # Georeference images
    local vrt_inputs=""
    if [ -f "$phs_img" ]; then
        gdal_translate -a_srs EPSG:4326 -a_ullr 97.0 21.0 106.0 15.0 \
            "$phs_img" "$output_dir/phs/rain_only_georef.tif" >/dev/null 2>&1
        vrt_inputs="$vrt_inputs $output_dir/phs/rain_only_georef.tif"
    fi
    
    if [ -f "$chn_img" ]; then
        gdal_translate -a_srs EPSG:4326 -a_ullr 97.0 21.0 106.0 15.0 \
            "$chn_img" "$output_dir/chn/rain_only_georef.tif" >/dev/null 2>&1
        vrt_inputs="$vrt_inputs $output_dir/chn/rain_only_georef.tif"
    fi
    
    if [ -f "$cri_img" ]; then
        gdal_translate -a_srs EPSG:4326 -a_ullr 97.0 21.0 106.0 15.0 \
            "$cri_img" "$output_dir/cri/rain_only_georef.tif" >/dev/null 2>&1
        vrt_inputs="$vrt_inputs $output_dir/cri/rain_only_georef.tif"
    fi
    
    # Skip if no inputs
    if [ -z "$vrt_inputs" ]; then
        echo "    ⚠️  No georeferenced files found for $timestamp, skipping..."
        return
    fi
    
    # Create VRT mosaic
    gdalbuildvrt -resolution highest \
        -hidenodata \
        -srcnodata "0 0 0 0" -vrtnodata "0 0 0 0" \
        "$output_dir/source_mosaic.vrt" \
        $vrt_inputs >/dev/null 2>&1
    
    # Set color interpretation
    gdal_edit -colorinterp_1 red -colorinterp_2 green -colorinterp_3 blue -colorinterp_4 alpha \
        "$output_dir/source_mosaic.vrt" >/dev/null 2>&1 || true
    
    # Warp to EPSG:3857
    gdalwarp -multi -wo NUM_THREADS=ALL_CPUS \
        -t_srs EPSG:3857 -r near \
        -srcalpha -dstalpha \
        -of GTiff -co PHOTOMETRIC=RGB -co ALPHA=YES \
        "$output_dir/source_mosaic.vrt" "$output_dir/mosaic_3857.tif" >/dev/null 2>&1
    
    # Convert to RGBA
    gdal_translate -b 1 -b 2 -b 3 -b 4 \
        "$output_dir/mosaic_3857.tif" "$output_dir/mosaic_3857_rgba.tif" >/dev/null 2>&1
    
    # Create tiles
    mkdir -p "$output_dir/tiles"
    gdal2tiles.py -z 5-11 -r near "$output_dir/mosaic_3857_rgba.tif" "$output_dir/tiles" >/dev/null 2>&1
    
    echo "    ✅ Tiles created at: $output_dir/tiles"
}

# Get number of CPU cores for parallel processing
MAX_JOBS=$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo "4")
MAX_JOBS=$((MAX_JOBS > 8 ? 8 : MAX_JOBS))  # Limit to 8 to avoid overwhelming system

echo "🚀 Starting fast parallel radar processing..."
echo "📊 Using $MAX_JOBS parallel jobs"
echo "==============================================="

echo "Step 1: Loading radar images..."
bash ./load-radar.sh
sleep 2

echo "==============================================="
echo "Step 2: Processing radar images in parallel..."
echo "==============================================="

# Check if radar_img directory exists
if [ ! -d "radar_img" ]; then
    echo "❌ Error: radar_img directory not found!"
    exit 1
fi

# Find all timestamp directories
timestamp_dirs=(radar_img/*/)
total_dirs=${#timestamp_dirs[@]}

if [ $total_dirs -eq 0 ]; then
    echo "❌ No timestamp directories found in radar_img/"
    exit 1
fi

echo "📁 Found $total_dirs timestamp directories to process"

# Process directories in parallel using xargs
printf '%s\n' "${timestamp_dirs[@]}" | \
    xargs -n 1 -P "$MAX_JOBS" -I {} bash -c 'process_timestamp "$@"' _ {}

echo "==============================================="
echo "✅ All tasks completed successfully!"
echo "==============================================="
echo "📊 Summary:"
echo "  - Downloaded radar images to: radar_img/"
echo "  - Processed images saved to: radar_process/"
echo "  - Georeferenced tiles saved to: out/"
echo ""

# Show results
if command -v tree >/dev/null 2>&1; then
    echo "📂 Tiles directory structure:"
    tree out/ -L 2 2>/dev/null
else
    echo "📂 Available tile sets:"
    find out/ -name "*.html" -o -name "tilemapresource.xml" | head -10
fi

echo ""
echo "🎉 All radar image processing and tile generation completed!"
echo "⏱️  Processing time: approximately $(date)"

# Export the function so it can be used by xargs
export -f process_timestamp
export -f create_tiles_for_timestamp
