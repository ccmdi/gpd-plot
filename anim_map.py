import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.font_manager as font_manager
import geopandas as gpd
import numpy as np
import argparse
import json
from pathlib import Path

def json_coordinates(data):
    if isinstance(data, list):
        return pd.DataFrame(data)
    elif isinstance(data, dict):
        if 'customCoordinates' in data:
            return pd.DataFrame(data['customCoordinates'])
        elif 'coordinates' in data:
            return pd.DataFrame(data['coordinates'])
        else:
            raise ValueError("Unknown JSON structure")
    else:
        raise ValueError("Invalid JSON data")

def plot_anim(args):
    # Configuration
    PATH = Path(args.file).resolve()
    ADM1_GEOJSON = r'Contiguous US.geojson'
    ADM2_GEOJSON = r'Contiguous USA states.geojson'
    FILE_CRS = "EPSG:4326"
    CONVERT_CRS = "ESRI:102003"

    LABEL_X, LABEL_Y = 0.5, 0.95
    LABEL_H_ALIGNMENT = 'center'
    LABEL_V_ALIGNMENT = 'top'
    LABEL_SIZE = 40

    MARGIN_TOP = 0.15
    MARGIN_LEFT = 0.05
    MARGIN_RIGHT = 0.05
    MARGIN_BOTTOM = 0.05
    
    FPS = 15
    UPDATE_INTERVAL_MS = 140

    MODE = "SHOW" # "SHOW" or "SAVE"
    PROGRESS = True
    
    
    file_name = PATH.stem

    # Read and process data
    if PATH.suffix.lower() == '.json':
        with open(PATH, 'r') as f:
            data = json.load(f)
        df = json_coordinates(data)
    else:  # Assume CSV for other file types
        df = pd.read_csv(PATH, skip_blank_lines=True)
        
    required_columns = ['timestamp', 'lat', 'lng']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"Input data must contain columns: {', '.join(required_columns)}")

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s').dt.floor('D')
    df = df.sort_values('timestamp')
    df['date_hour'] = df['timestamp'].apply(lambda x: x.replace(minute=0, second=0)) # Old logic
    date_range = pd.date_range(start=df['date_hour'].min(), end=df['date_hour'].max(), freq='D')

    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lng, df.lat), crs=FILE_CRS).to_crs(CONVERT_CRS)
    gdf.set_index('date_hour', inplace=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Load and plot basemap
    country = gpd.read_file(ADM1_GEOJSON).set_crs("epsg:4326").to_crs(CONVERT_CRS)
    country.plot(ax=ax, color='none', edgecolor='white', linewidth=0.25)
    subdivisions = gpd.read_file(ADM2_GEOJSON).set_crs("epsg:4326").to_crs(CONVERT_CRS)
    subdivisions.plot(ax=ax, edgecolor='white', facecolor='none', linewidth=0.025)

    # Initialize scatter plot and text
    sc = ax.scatter([], [], s=1)
    text = ax.text(LABEL_X, LABEL_Y, '', transform=ax.transAxes, color='white', fontsize=LABEL_SIZE, ha=LABEL_H_ALIGNMENT, va=LABEL_V_ALIGNMENT)

    # Set plot limits and style
    minx, miny, maxx, maxy = country.total_bounds
    width = maxx - minx
    height = maxy - miny

    minx -= width * MARGIN_LEFT
    maxx += width * MARGIN_RIGHT
    miny -= height * MARGIN_BOTTOM
    maxy += height * MARGIN_TOP
    
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    plt.margins(0)
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    fig.patch.set_facecolor('black')
    fig.canvas.toolbar.pack_forget()
    fig.canvas.manager.set_window_title(file_name)
    ax.set_facecolor('black')
    ax.set_aspect('equal')

    # Animation
    def init():
        sc.set_offsets(np.empty((0, 2)))
        text.set_text('')
        return [sc, text]

    def update(frame):
        current_time = date_range[frame]
        data = gdf.loc[:current_time]
        offsets = np.column_stack((data.geometry.x, data.geometry.y))
        sc.set_offsets(offsets)
        text.set_text(current_time.strftime("%Y-%m-%d"))
        if PROGRESS: print(f"{frame+1}/{len(date_range)}", end='\r')
        return [sc, text]

    # Create and display the animation
    ani = animation.FuncAnimation(fig, update, frames=len(date_range), init_func=init, blit=True, interval=UPDATE_INTERVAL_MS)

    video_length_seconds = len(date_range) / FPS
    minutes, seconds = divmod(video_length_seconds, 60)
    print(f"Total video length: {int(minutes)}:{seconds:.2f}")
    
    if MODE == "SHOW":
        plt.show()
    elif MODE == "SAVE":
        ani.save(f'{file_name}.mp4', writer='ffmpeg', fps=FPS, dpi=300)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str, required=True)
    args = parser.parse_args()
    plot_anim(args)