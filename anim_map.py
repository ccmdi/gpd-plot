import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.font_manager as fm
import matplotlib.colors as mcolors
from matplotlib.cm import ScalarMappable
import geopandas as gpd
import numpy as np
import os
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

def font_by_name(font_name):
    font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    for font_path in font_paths:
        font = fm.FontProperties(fname=font_path)
        if font.get_name().lower() == font_name.lower():
            return font_path
    return None

def load_background_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    df = json_coordinates(data)

    # Extract panoDate from extra field
    if 'imageDate' not in df.columns:
        df['imageDate'] = df['extra'].apply(lambda x: x['panoDate'])
        
    # Convert panoDate to datetime
    df['imageDate'] = pd.to_datetime(df['imageDate'])
    
    return df

def plot_anim(args):
    # Configuration
    PATH = Path(args.file).resolve()
    ADM1_GEOJSON = r'proj/US/Alaska.geojson'
    ADM2_GEOJSON = r'proj/US/Alaska.geojson'
    FILE_CRS = "EPSG:4326"
    CONVERT_CRS = "ESRI:102006"

    LABEL_X, LABEL_Y = 0.2, 1
    LABEL_H_ALIGNMENT = 'center'
    LABEL_V_ALIGNMENT = 'top'
    LABEL_SIZE = 40
    LABEL_FONT = "Nunito Sans"

    MARGIN_TOP = 0.15
    MARGIN_LEFT = 0.05
    MARGIN_RIGHT = 0.05
    MARGIN_BOTTOM = 0.05
    
    DECAY_YEARS = 5  # Number of years over which opacity reduces to 50%
    MIN_OPACITY = 0.2  # Minimum opacity for very old point

    FPS = 15
    UPDATE_INTERVAL_MS = 140
    
    file_name = PATH.stem
    font_path = font_by_name(LABEL_FONT)
    if font_path:
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
        print(f"Loaded font: {font_prop.get_name()}")
    else:
        print("Failed to load font")

    # Read and process main data
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

    # Load background data
    bg_data_list = []
    if args.background_data:
        for bg_path in args.background_data:
            bg_data_list.append(load_background_data(bg_path))
    bg_data = pd.concat(bg_data_list) if bg_data_list else pd.DataFrame()
    
    if args.background_data and not bg_data.empty:
        bg_data['imageDate'] = bg_data['imageDate'].dt.to_period('M').dt.to_timestamp()

    # Process date ranges and output JSON
    date_ranges = df.groupby(df['timestamp'].dt.year)['timestamp'].agg(['min', 'max'])
    date_ranges_json = {
        str(year): {
            "earliest": min_date.strftime("%Y-%m-%d"),
            "latest": max_date.strftime("%Y-%m-%d")
        }
        for year, (min_date, max_date) in date_ranges.iterrows()
    }
    
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    output_file = script_dir / f"DATE_RANGES.json"
    with open(output_file, 'w') as f:
        json.dump(date_ranges_json, f, indent=2)
    
    print(f"Date ranges have been written to {output_file}")

    df['date_hour'] = df['timestamp'].apply(lambda x: x.replace(minute=0, second=0))
    if bg_data.empty:
        date_range = pd.date_range(start=df['date_hour'].min(), end=df['date_hour'].max(), freq='D')
    else:
        date_range = pd.date_range(start=min(df['date_hour'].min(), bg_data['imageDate'].min()), 
                                   end=max(df['date_hour'].max(), bg_data['imageDate'].max()), 
                                   freq='D')

    # Assume 'year' is extracted from the timestamp
    df['year'] = df['timestamp'].dt.year
    if not bg_data.empty:
        bg_data['year'] = bg_data['imageDate'].dt.year

    # Create a color map based on the year
    years = np.union1d(df['year'].unique(), bg_data['year'].unique() if not bg_data.empty else [])

    min_year = args.min_year if args.min_year is not None else years.min()
    max_year = args.max_year if args.max_year is not None else years.max()

    color_map = plt.cm.rainbow
    norm = mcolors.Normalize(vmin=min_year, vmax=max_year)

    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lng, df.lat), crs=FILE_CRS).to_crs(CONVERT_CRS)
    gdf.set_index('date_hour', inplace=True)

    if not bg_data.empty:
        bg_gdf = gpd.GeoDataFrame(bg_data, geometry=gpd.points_from_xy(bg_data.lng, bg_data.lat), crs=FILE_CRS).to_crs(CONVERT_CRS)
        bg_gdf['imageDate'] = pd.to_datetime(bg_gdf['imageDate'])
        bg_gdf['alpha'] = 0.0

    fig, ax = plt.subplots(figsize=(10, 6))

    # Load and plot basemap
    country = gpd.read_file(ADM1_GEOJSON).set_crs("epsg:4326").to_crs(CONVERT_CRS)
    country.plot(ax=ax, color='none', edgecolor='white', linewidth=0.25)
    subdivisions = gpd.read_file(ADM2_GEOJSON).to_crs(CONVERT_CRS)
    subdivisions.plot(ax=ax, edgecolor='white', facecolor='none', linewidth=0.025)

    # Initialize scatter plots and text
    bg_sc = ax.scatter([], [], s=3, c=[], cmap=color_map, norm=norm, alpha=0.3)
    sc = ax.scatter([], [], s=1.5, c=[], cmap=color_map, norm=norm)
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
    def calculate_opacity(point_dates, current_date):
        """Calculate opacity based on age of points."""
        if len(point_dates) == 0:
            return np.array([])
            
        point_dates = np.array(point_dates, dtype='datetime64[ns]')
        current_date = np.datetime64(current_date)
        
        # Calculate age in days
        age_days = (current_date - point_dates).astype('timedelta64[D]').astype(np.float64)
        decay_days = DECAY_YEARS * 365
        
        opacity = np.exp(-age_days / decay_days)
        
        opacity = np.maximum(opacity, MIN_OPACITY)
        
        return opacity
    
    def init():
        bg_sc.set_offsets(np.empty((0, 2)))
        bg_sc.set_array(np.array([]))
        sc.set_offsets(np.empty((0, 2)))
        sc.set_array(np.array([]))
        text.set_text('')
        return [bg_sc, sc, text]

    # Store all points and their dates
    all_points = []
    all_dates = []
    all_years = []

    def update(frame):
        nonlocal all_points, all_dates, all_years
        current_time = date_range[frame]
        
        if not bg_data.empty:
            # Update background data
            month_start = current_time.replace(day=1)
            next_month = month_start + pd.offsets.MonthEnd(1)
            month_progress = (current_time - month_start) / (next_month - month_start)

            current_month_mask = (bg_gdf['imageDate'].dt.to_period('M') == current_time.to_period('M'))
            bg_gdf.loc[current_month_mask, 'alpha'] = month_progress

            prev_month_mask = (bg_gdf['imageDate'].dt.to_period('M') == (current_time - pd.offsets.MonthBegin(1)).to_period('M'))
            bg_gdf.loc[prev_month_mask, 'alpha'] = 1.0
            
            mask_visible = (bg_gdf['imageDate'].dt.to_period('M') <= current_time.to_period('M'))
            bg_data_visible = bg_gdf[mask_visible]
            
            if not bg_data_visible.empty:
                # Calculate fade-in alphas
                fade_in_alphas = np.ones(len(bg_data_visible))
                current_month_mask = (bg_data_visible['imageDate'].dt.to_period('M') == current_time.to_period('M'))
                fade_in_alphas[current_month_mask] = month_progress
                
                # Calculate age-based decay alphas
                age_days = (current_time - bg_data_visible['imageDate']).dt.total_seconds() / (24 * 60 * 60)
                decay_days = DECAY_YEARS * 365
                decay_alphas = np.exp(-age_days / decay_days)
                decay_alphas = np.maximum(decay_alphas, MIN_OPACITY)
                
                # Combine both alpha effects
                months_old = ((current_time - bg_data_visible['imageDate']).dt.total_seconds() / (30 * 24 * 60 * 60))
                MIN_FADE = 0.1  # Points will never go below 10% opacity
                fade_out_alphas = (1 - (months_old / 6)).clip(MIN_FADE, 1)
                
                final_alphas = fade_in_alphas * fade_out_alphas * 0.5
                
                # Update scatter plot
                bg_offsets = np.column_stack((bg_data_visible.geometry.x, bg_data_visible.geometry.y))
                bg_sc.set_offsets(bg_offsets)
                bg_sc.set_array(bg_data_visible['imageDate'].dt.year)
                bg_sc.set_alpha(final_alphas)
        
        # Update main data with time decay
        if frame == 0:
            data = gdf.loc[:current_time]
            if not data.empty:
                offsets = np.column_stack((data.geometry.x, data.geometry.y))
                all_points = offsets.tolist()
                all_dates = data.index.tolist()
                all_years = data.index.year.tolist()
        else:
            new_data = gdf.loc[date_range[frame-1]:current_time]
            if not new_data.empty:
                new_offsets = np.column_stack((new_data.geometry.x, new_data.geometry.y))
                all_points.extend(new_offsets.tolist())
                all_dates.extend(new_data.index.tolist())
                all_years.extend(new_data.index.year.tolist())
        
        if all_points:  # Only update if we have points
            offsets = np.array(all_points)
            years = np.array(all_years)
            
            # Calculate opacities for all points
            opacities = calculate_opacity(all_dates, current_time)
            
            sc.set_offsets(offsets)
            sc.set_array(years)
            if len(opacities) > 0:
                sc.set_alpha(opacities)
        
        text.set_text(current_time.strftime("%Y-%m-%d"))
        if args.progress:
            print(f"{frame+1}/{len(date_range)}", end='\r')
        return [bg_sc, sc, text]

    if args.final_frame:
        update(len(date_range) - 1)
        plt.show()
    else:
        ani = animation.FuncAnimation(fig, update, frames=len(date_range), init_func=init, blit=True, interval=UPDATE_INTERVAL_MS)

        video_length_seconds = len(date_range) / FPS
        minutes, seconds = divmod(video_length_seconds, 60)
        print(f"Total video length: {int(minutes)}:{seconds:.2f}")
        
        if args.mode.lower() == "show":
            plt.show()
        elif args.mode.lower() == "save":
            ani.save(f'videos/{file_name}.mp4', writer='ffmpeg', fps=FPS, dpi=300)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str, required=True)
    parser.add_argument('--background-data', type=str, nargs='*', help='Paths to background data files')
    parser.add_argument('--min-year', type=int, help='Minimum year for color scale')
    parser.add_argument('--max-year', type=int, help='Maximum year for color scale')
    parser.add_argument('--final-frame', action='store_true', help='Render only the final frame instead of the animation')
    parser.add_argument('--mode', type=str, choices=['show', 'save'], default='show', help='Mode to run the script in')
    parser.add_argument('--progress', action='store_true', help='Show progress during animation')
    args = parser.parse_args()
    plot_anim(args)