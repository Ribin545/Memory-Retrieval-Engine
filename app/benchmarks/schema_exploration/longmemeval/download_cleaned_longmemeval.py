import os
import requests
from tqdm import tqdm
import argparse

def download_file(url, dest_path, force=False):
    if os.path.exists(dest_path) and not force:
        print(f"File already exists: {dest_path}. Skipping download.")
        return

    print(f"Downloading from {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    with open(dest_path, 'wb') as f, tqdm(
        desc=os.path.basename(dest_path),
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            size = f.write(chunk)
            bar.update(size)

    print(f"Download complete: {dest_path}")
    print(f"Final file size: {os.path.getsize(dest_path)} bytes")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force download even if file exists")
    args = parser.parse_args()

    URL = "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
    DEST = "data/external/longmemeval_cleaned/longmemeval_s_cleaned.json"

    download_file(URL, DEST, args.force)
