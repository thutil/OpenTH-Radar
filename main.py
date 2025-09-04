import os
import time
from fastapi import FastAPI
import socket

app = FastAPI()


@app.get("/")
def read_root():
    return {"status": "OK"}


@app.get("/api/v1/weather")
def get_weather_data():

    radar_dir = "/Users/bankjirapan/MyDeveloper/OpenTH-Radar/radar"

    if not os.path.exists(radar_dir):
        return {"error": "Radar directory not found"}

    current_time = int(time.time())
    six_hours_ago = current_time - (6 * 60 * 60)  # Exclude data older than 6h
    radar_folders = []
    try:
        for folder_name in os.listdir(radar_dir):
            folder_path = os.path.join(radar_dir, folder_name)
            if os.path.isdir(folder_path) and folder_name.isdigit():
                timestamp = int(folder_name)
                # Include only folders within the last 6 hours
                if timestamp >= six_hours_ago:
                    radar_folders.append(timestamp)
    except Exception as e:
        return {"error": f"Failed to read radar directory: {str(e)}"}

    radar_folders.sort()

    past_data = []
    for timestamp in radar_folders:
        past_data.append({
            "time": timestamp,
            "path": f"/radar/{timestamp}"
        })

    response = {
        "version": "1.0",
        "generated": current_time,
        "host": socket.gethostname(),
        "radar": {
            "past": past_data
        }
    }

    return response
