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

# Initialize WebDriver with explicit ChromeDriver path if needed
try:
    driver = webdriver.Chrome()
except Exception as e:
    logging.error(f"Failed to initialize WebDriver: {e}")
    exit(1)

base_url = "https://www.bd-pratidin.com/"
start_url = base_url

# Create folder to store images
output_folder = "jugantor_images"
os.makedirs(output_folder, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

visited_urls = set()
image_urls = set()
urls_to_visit = deque([start_url])


def extract_images_from_page(url):
    try:
        logging.info(f"Visiting: {url}")
        driver.get(url)
        time.sleep(2)

        # Scroll to load dynamic content
        for _ in range(5):
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            time.sleep(1)

        # Extract images
        images = driver.find_elements(By.TAG_NAME, "img")
        logging.info(f"Found {len(images)} image elements on {url}")

        for img in images:
            try:
                image_url = img.get_attribute("src")
                if image_url:
                    image_url = urljoin(url, image_url)
                    if image_url.startswith(('http://', 'https://')):
                        image_urls.add(image_url)
                        logging.info(f"Added image URL: {image_url}")
            except Exception as e:
                logging.error(f"Error extracting image: {e}")

        # Extract links
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
max_pages = 50  # Reduced for testing
with tqdm(total=max_pages, desc="Crawling pages") as pbar:
    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.popleft()
        if current_url not in visited_urls:
            visited_urls.add(current_url)
            extract_images_from_page(current_url)
            pbar.update(1)

driver.quit()
logging.info(f"Total unique image URLs found: {len(image_urls)}")

# Download images
for idx, image_url in enumerate(tqdm(image_urls, desc="Downloading images")):
    try:
        img_name = os.path.join(output_folder, f"image_{idx:03d}.jpg")
        logging.info(f"Attempting to download: {image_url}")

        response = requests.get(
            image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        content_length = response.headers.get('content-length', 'Unknown')
        logging.info(
            f"Response for {image_url}: Status={response.status_code}, Type={content_type}, Size={content_length}")

        if response.status_code == 200 and 'image' in content_type.lower():
            with open(img_name, 'wb') as file:
                total_size = 0
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
                        total_size += len(chunk)
            if total_size > 0:
                logging.info(
                    f"Successfully downloaded {image_url} as {img_name} ({total_size} bytes)")
            else:
                logging.warning(f"Downloaded {image_url} but file is empty")
                os.remove(img_name) if os.path.exists(img_name) else None
        else:
            logging.warning(
                f"Skipped {image_url}: Status={response.status_code}, Type={content_type}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error downloading {image_url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error downloading {image_url}: {e}")

# Check folder contents
downloaded_files = [f for f in os.listdir(output_folder) if f.endswith('.jpg')]
logging.info(
    f"Download Completed! Found {len(downloaded_files)} images in '{output_folder}'")
print(
    f"✅ Process Complete. Check '{output_folder}' for {len(downloaded_files)} images")
