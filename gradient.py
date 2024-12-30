# Creates a gradient bar to add to final visualization

import matplotlib.pyplot as plt
import numpy as np
import argparse
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
import matplotlib.font_manager as fm

def font_by_name(font_name):
    font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    for font_path in font_paths:
        font = fm.FontProperties(fname=font_path)
        if font.get_name().lower() == font_name.lower():
            return font_path
    return None

def plot_year_gradient(min_year, max_year, output_file):
    # Set up font
    LABEL_FONT = "Nunito Sans"
    font_path = font_by_name(LABEL_FONT)
    if font_path:
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
    
    # Create figure with controlled size
    fig = plt.figure(figsize=(10, 0.6), facecolor='black')
    ax = fig.add_axes([0.05, 0.4, 0.9, 0.3])
    ax.set_facecolor('black')
    
    # Create gradient data
    gradient = np.linspace(0, 1, 256).reshape(1, -1)
    
    # Plot the gradient
    ax.imshow(gradient, aspect='auto', cmap='rainbow')
    
    # Create custom ticks for years
    num_ticks = 5
    tick_positions = np.linspace(0, 255, num_ticks)
    tick_labels = np.linspace(min_year, max_year, num_ticks, dtype=int)
    
    # Set ticks and remove y-axis
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, color='white', fontsize=14)
    ax.set_yticks([])
    
    # Remove spines
    for spine in ax.spines.values():
        spine.set_visible(False)
    
    # Save with exact dimensions
    plt.savefig(output_file, 
                facecolor='black',
                bbox_inches='tight',
                pad_inches=0.1,
                dpi=300)
    plt.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--min-year', type=int, required=True)
    parser.add_argument('--max-year', type=int, required=True)
    parser.add_argument('--output', type=str, default='year_gradient.png')
    args = parser.parse_args()
    
    plot_year_gradient(args.min_year, args.max_year, args.output)