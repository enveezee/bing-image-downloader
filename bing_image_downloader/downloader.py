
import os
import requests
from typing import List
from bing_image_downloader.data_model import ImageData

class Downloader:
    def __init__(self, download_directory: str):
        self.download_directory = download_directory
        if not os.path.exists(self.download_directory):
            os.makedirs(self.download_directory)

    def download(self, image_data: ImageData):
        if image_data.image_source_url:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            try:
                print(f"[DEBUG] Attempting to download: {image_data.image_source_url}")
                response = requests.get(image_data.image_source_url, stream=True, headers=headers, timeout=10)
                response.raise_for_status() # Raise an exception for bad status codes

                file_extension = os.path.splitext(image_data.image_source_url)[1]
                if not file_extension or len(file_extension) > 5:
                    file_extension = f".{image_data.file_type.lower()}" if image_data.file_type else ".jpg"

                sanitized_title = "".join(c for c in image_data.title if c.isalnum() or c in (' ', '-')).rstrip()
                if not sanitized_title:
                    sanitized_title = f"image_{image_data.data_idx}"

                file_path = os.path.join(self.download_directory, f"{sanitized_title}{file_extension}")

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                image_data.downloaded_path = file_path
                print(f"Successfully downloaded {file_path}")

            except requests.exceptions.Timeout as e:
                raise Exception(f"Download timed out for {image_data.image_source_url}: {e}")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Failed to download {image_data.image_source_url}: {e}")
            except Exception as e:
                raise Exception(f"An unexpected error occurred during download of {image_data.image_source_url}: {e}")
