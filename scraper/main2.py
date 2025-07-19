import os
import requests
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from urllib.parse import urljoin
from collections import deque
import logging

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize WebDriver with options
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Headless mode for efficiency
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    logging.error(f"Failed to initialize WebDriver: {e}")
    exit(1)

base_url = "https://www.amarsangbad.com/"
# Start at Photo Gallery page
start_url = "https://www.amarsangbad.com/photo-gallery"

# Create folder to store images
output_folder = "amarsonbad_images"
os.makedirs(output_folder, exist_ok=True)
logging.info(f"Output folder created at: {os.path.abspath(output_folder)}")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': base_url,
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
}

visited_urls = set()
urls_to_visit = deque([start_url])
image_count = 0


def download_image(image_url, idx):
    global image_count
    img_name = os.path.join(output_folder, f"image_{idx:03d}.jpg")
    try:
        logging.info(f"Downloading: {image_url} to {img_name}")
        response = requests.get(
            image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if 'image' in content_type.lower():
            with open(img_name, 'wb') as file:
                total_size = 0
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
                        total_size += len(chunk)
            if total_size > 0:
                logging.info(
                    f"Successfully downloaded {image_url} ({total_size} bytes)")
                image_count += 1
            else:
                logging.warning(f"Empty file for {image_url}")
                os.remove(img_name) if os.path.exists(img_name) else None
        else:
            logging.warning(
                f"Skipped {image_url}: Not an image (Type={content_type})")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error downloading {image_url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error downloading {image_url}: {e}")


def scrape_images_from_page(url):
    try:
        logging.info(f"Visiting: {url}")
        driver.get(url)

        # Quick scroll to trigger lazy loading (no wait)
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(5):
            body.send_keys(Keys.END)

        # Find all images on the page (only <img> tags)
        images = driver.find_elements(By.TAG_NAME, "img")
        logging.info(f"Found {len(images)} images on {url}")

        # Detect and download images immediately
        seen_urls = set()  # Avoid duplicates on this page
        for idx, img in enumerate(images, start=image_count):
            try:
                image_url = img.get_attribute(
                    "src") or img.get_attribute("data-src")
                if image_url:
                    image_url = urljoin(url, image_url)
                    if image_url.startswith(('http://', 'https://')) and image_url not in seen_urls:
                        logging.info(f"Detected image URL: {image_url}")
                        download_image(image_url, idx)
                        seen_urls.add(image_url)
            except Exception as e:
                logging.error(f"Error processing image: {e}")

        # Extract links for further crawling
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and base_url in href and href not in visited_urls:
                    urls_to_visit.append(href)
            except Exception as e:
                logging.error(f"Error extracting link: {e}")

    except Exception as e:
        logging.error(f"Error processing page {url}: {e}")


# Crawl the website and scrape images (max 100 pages)
max_pages = 100
logging.info(f"Starting crawl with a limit of {max_pages} pages...")
with tqdm(total=max_pages, desc="Crawling pages") as pbar:
    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.popleft()
        if current_url not in visited_urls:
            visited_urls.add(current_url)
            scrape_images_from_page(current_url)
            pbar.update(1)

driver.quit()
downloaded_files = [f for f in os.listdir(output_folder) if f.endswith('.jpg')]
logging.info(
    f"Process Complete! Found {len(downloaded_files)} images in '{output_folder}'")
print(f"✅ Done. {image_count} images downloaded to '{output_folder}'")
