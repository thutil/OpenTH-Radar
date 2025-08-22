#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source .venv/bin/activate

echo "==============================================="
echo "Step 1: Loading radar images..."
echo "==============================================="

# Run the load-radar.sh script
bash ./load-radar.sh

# Wait a moment for files to be created
sleep 2

echo "==============================================="
echo "Step 2: Processing radar images..."
echo "==============================================="

# Process radar images from radar_img directory using templates from georeferencing directory

echo "Starting radar image processing..."
echo "Looking for directories in radar_img..."

# Check if radar_img directory exists
if [ ! -d "radar_img" ]; then
    echo "Error: radar_img directory not found!"
    exit 1
fi

# List contents for debugging
echo "Contents of radar_img:"
ls -la radar_img/

# Find all timestamp directories in radar_img
for timestamp_dir in radar_img/*/; do
    if [ -d "$timestamp_dir" ]; then
        echo "Processing directory: $timestamp_dir"
        
        # Extract timestamp from directory path
        timestamp=$(basename "$timestamp_dir")
        
        # Run the radar processing script with radar_process output directory
        python3 radar_process.py \
            --template_dir ./georeferencing \
            --input_dir "$timestamp_dir" \
            --workdir "./radar_process/$timestamp" \
            --s_min 200 \
            --v_min 70 \
            --disk_shrink 0.96 \
            --left_crop_frac 0.18
            
        echo "Completed processing: $timestamp_dir"
        echo "Output saved to: ./radar_process/$timestamp"
        echo "----------------------------------------"
    fi
done

echo "==============================================="
echo "All tasks completed successfully!"
echo "==============================================="
echo "Summary:"
echo "- Downloaded radar images to: radar_img/"
echo "- Processed images saved to: radar_process/"
echo ""
echo "Radar process directory structure:"
tree radar_process/ 2>/dev/null || find radar_process/ -type f

echo "All radar image processing completed!"


python3 radar_tuning.py \
  --input radar_process/1755859800/chn240_HQ_latest_rain_only.png \
  --out rain_smooth.png \
  --clahe 2.0