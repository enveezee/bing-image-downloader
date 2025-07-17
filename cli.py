
import argparse
from bing_image_downloader.scraper import BingImageScraper
from bing_image_downloader.downloader import Downloader

def main():
    parser = argparse.ArgumentParser(description="Bing Image Scraper and Downloader CLI")
    parser.add_argument("query", type=str, help="The search query for images.")
    parser.add_argument("--download_dir", type=str, default="downloads", help="The directory to save downloaded images.")
    parser.add_argument("--max_images", type=int, default=20, help="The maximum number of images to download.")
    args = parser.parse_args()

    print(f"Searching for '{args.query}'...")
    scraper = BingImageScraper()
    scraper.search(args.query)
    image_data = scraper.get_image_data(max_images=args.max_images)

    if image_data:
        print(f"Found {len(image_data)} images.")
        downloader = Downloader(args.download_dir)
        downloader.download(image_data)
        print("Download complete.")
    else:
        print("No images found.")

if __name__ == "__main__":
    main()
