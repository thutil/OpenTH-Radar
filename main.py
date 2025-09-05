import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image
import io
from fastapi.responses import HTMLResponse

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ลบการ mount static files
# app.mount("/radar", StaticFiles(directory="radar"), name="radar")

@app.get("/", response_class=HTMLResponse)
def read_root():
    views_dir = os.path.join(os.path.dirname(__file__), "views")
    index_path = os.path.join(views_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    else:
        return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

def create_empty_tile():
    img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG', optimize=True)
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()


@app.get("/radar/{timestamp}/{zoom}/{x}/{y}.png")
def serve_tile(timestamp: str, zoom: str, x: str, y: str):
    radar_dir = "/app/radar"
    tile_path = f"{radar_dir}/{timestamp}/{zoom}/{x}/{y}.png"
    if os.path.exists(tile_path):
        return FileResponse(
            tile_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    else:
        empty_tile = create_empty_tile()
        return Response(
            content=empty_tile,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"}
        )


@app.get("/api/v1/weather")
def get_weather_data():

    radar_dir = "/app/radar"

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
        "host": "http://localhost:8000",
        "radar": {
            "past": past_data
        }
    }

    return response
