# !/usr/bin/env bash

# Base URL for radar images
baseURL="https://weather.tmd.go.th"

# List of filenames to download
filenames=("chn/chn240_HQ_latest.png" "phs/phs240_HQ_latest.png" "cri/cri240_HQ_latest.png")

# Get current Unix time and round to the nearest 10 minutes
currentTime=$(date +%s)
roundedTime=$(( (currentTime / 600) * 600 ))

printf "Rounded time: %d\n" "$roundedTime"

# Check if radar_img directory exists, if not, create it
if [ ! -d "./radar_img" ]; then
    mkdir -p "./radar_img"
fi

# Check if timestamp directory exists, if not, create it
if [ ! -d "./radar_img/$roundedTime" ]; then
    mkdir -p "./radar_img/$roundedTime"
fi

# Directory to save images (rounded Unix time)
outputDir="./radar_img/$roundedTime"

# Create output directory if it doesn't exist
mkdir -p "$outputDir"

# Download each file
for filename in "${filenames[@]}"; do
    printf "Downloading: %s/%s\n" "$baseURL" "$filename"
    outputFile="$outputDir/$(basename "$filename")"
    curl -o "$outputFile" "$baseURL/$filename"
done