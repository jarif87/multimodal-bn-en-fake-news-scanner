import os
import time
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

# Initialize WebDriver
try:
    driver = webdriver.Chrome()
except Exception as e:
    logging.error(f"Failed to initialize WebDriver: {e}")
    exit(1)

base_url = "https://www.bd-journal.com/"
start_url = base_url

# Create folder to store images
output_folder = "bdjournal_images"
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
        logging.info(f"Attempting to download: {image_url} to {img_name}")
        response = requests.get(
            image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        content_length = response.headers.get('content-length', 'Unknown')
        logging.info(
            f"Response: Status={response.status_code}, Type={content_type}, Size={content_length}")

        if response.status_code == 200 and 'image' in content_type.lower():
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
                f"Skipped {image_url}: Status={response.status_code}, Type={content_type}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error downloading {image_url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error downloading {image_url}: {e}")


def extract_and_download_from_page(url):
    try:
        logging.info(f"Visiting: {url}")
        driver.get(url)
        time.sleep(2)

        for _ in range(5):
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            time.sleep(1)

        images = driver.find_elements(By.TAG_NAME, "img")
        logging.info(f"Found {len(images)} image elements on {url}")

        idx = image_count
        for img in images:
            try:
                image_url = img.get_attribute("src")
                if image_url:
                    image_url = urljoin(url, image_url)
                    if image_url.startswith(('http://', 'https://')):
                        logging.info(f"Found image URL: {image_url}")
                        download_image(image_url, idx)
                        idx += 1
            except Exception as e:
                logging.error(f"Error extracting image: {e}")

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


# Crawl the website
max_pages = 50
with tqdm(total=max_pages, desc="Crawling pages") as pbar:
    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.popleft()
        if current_url not in visited_urls:
            visited_urls.add(current_url)
            extract_and_download_from_page(current_url)
            pbar.update(1)

driver.quit()
downloaded_files = [f for f in os.listdir(output_folder) if f.endswith('.jpg')]
logging.info(
    f"Process Complete! Found {len(downloaded_files)} images in '{output_folder}'")
print(f"✅ Done. {image_count} images downloaded to '{output_folder}'")
