# !/usr/bin/env bash

# Base URL for radar images
baseURL="https://weather.tmd.go.th"

# List of filenames to download
filenames=("chn/chn240_HQ_latest.png" "phs/phs240_HQ_latest.png" "cri/cri240_HQ_latest.png")

# Get current Unix time and round to the nearest 10 minutes
currentTime=$(date +%s)
roundedTime=$(( (currentTime / 600) * 600 ))

# Directory to save images (rounded Unix time)
outputDir="../raw_radar/$roundedTime"

# Create output directory if it doesn't exist
mkdir -p "$outputDir"

# Download each file
for filename in "${filenames[@]}"; do
    printf "Downloading: %s/%s\n" "$baseURL" "$filename"
    outputFile="$outputDir/$(basename "$filename")"
    curl -o "$outputFile" "$baseURL/$filename"
done