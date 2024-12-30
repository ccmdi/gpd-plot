import json
import argparse
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

def parse_date(date_string: str) -> datetime:
    return datetime.strptime(date_string, "%Y-%m")

def round_coordinates(lat: float, lng: float, precision: int = 3) -> Tuple[float, float]:
    return (round(lat, precision), round(lng, precision))

def process_panoramas(data: Dict[str, List[Dict]], coordinate_precision: int = 3) -> List[Dict]:
    location_groups = defaultdict(list)
    for pano in data['customCoordinates']:
        location = round_coordinates(pano['lat'], pano['lng'], coordinate_precision)
        location_groups[location].append(pano)
   
    return [
        min(panos, key=lambda x: parse_date(x['extra']['panoDate'] if 'extra' in x else x['imageDate']))
        for panos in location_groups.values()
    ]

def get_default_output_filename(input_file: str) -> str:
    base, ext = os.path.splitext(input_file)
    return f"{base}_backdated{ext}"

def main():
    parser = argparse.ArgumentParser(description="Process panorama data to keep only the oldest panorama for each location.")
    parser.add_argument("input_file", help="Input JSON file containing panorama data")
    parser.add_argument("-o", "--output_file", help="Output JSON file to save processed data (default: input_file_backdated.json)")
    parser.add_argument("-p", "--precision", type=int, default=3, help="Coordinate rounding precision (default: 3)")
    args = parser.parse_args()

    if not args.output_file:
        args.output_file = get_default_output_filename(args.input_file)

    try:
        with open(args.input_file, 'r') as file:
            json_data = json.load(file)
    except json.JSONDecodeError:
        print(f"Error: {args.input_file} is not a valid JSON file.")
        return
    except FileNotFoundError:
        print(f"Error: {args.input_file} not found.")
        return

    processed_panoramas = process_panoramas(json_data, args.precision)
    output_data = {"customCoordinates": processed_panoramas}

    with open(args.output_file, 'w') as file:
        json.dump(output_data, file, indent=2)

    print(f"Processed {len(json_data['customCoordinates'])} panoramas.")
    print(f"Kept {len(processed_panoramas)} oldest panoramas.")
    print(f"Results saved to '{args.output_file}'.")

if __name__ == "__main__":
    main()