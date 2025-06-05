import os
import json
import glob
import sys
import time
import argparse


def get_json_files(folder_path):
    json_files = sorted(
        glob.glob(os.path.join(folder_path, "[0-9]" * 8 + ".json")) + \
        glob.glob(os.path.join(folder_path, "[0-9]" * 6 + ".json"))
    )
    return json_files


def load_json_content(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            return "[EMPTY JSON]"
        
        items = []
        for item in data:
            if "content" in item:
                if isinstance(item["content"], list):
                    for content in item["content"]:
                        if content["type"] == "text":
                            items.append(content["text"])
                        if content["type"] == "image_url":
                            items.append("[IMAGE]")
                elif isinstance(item["content"], str):
                    items.append(item["content"])
            else:
                items.append(f"total_cost: {item['total_cost']}")
        contents = ("\n" + "-" * 50 + "\n").join(items)
        return contents
    except Exception as e:
        return f"Error: {e}"


def main(folder_path):
    json_files = get_json_files(folder_path)
    if not json_files:
        print("No JSON files found.")
        return

    index = 0

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print("=" * 50)
        print(load_json_content(json_files[index]))
        print("-" * 50)
        print(f"Viewing file: {json_files[index]} ({index}/{len(json_files) - 1})")
        print("Press A(Left)/D(Right) to navigate, Q to quit.")

        line = input()
        key = line.strip().lower()
        json_files = get_json_files(folder_path)
        if key == 'q':
            break
        elif key == 'd' and index < len(json_files) - 1:
            index += 1
        elif key == 'a' and index > 0:
            index -= 1
        elif key == 'r':
            json_files = get_json_files(folder_path)
            print("Reloaded JSON file list.")
        elif key.isdigit():
            index = min(max(0, int(key)), len(json_files) - 1)

        time.sleep(0.1)
        print("Reloaded JSON file list.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JSON Viewer")
    parser.add_argument("--path", type=str, required=True, help="Path to JSON files folder")
    args = parser.parse_args()

    main(args.path)