import os
import time
import requests
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urljoin
from collections import deque
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize WebDriver with options
options = webdriver.ChromeOptions()
# Disable headless mode for debugging (re-enable once working)
# options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')  # Ensure full rendering
options.add_argument('--disable-extensions')  # Avoid interference
try:
    driver = webdriver.Chrome(options=options)
    logging.info("WebDriver initialized successfully")
except Exception as e:
    logging.error(
        f"Failed to initialize WebDriver: {e}. Ensure ChromeDriver matches your Chrome version.")
    exit(1)

base_url = "https://www.washingtonpost.com/?reload=true&_=1743947820950"
start_url = base_url

# Create folder to store images
# Fixed typo from "sonbadprotidin_images"
output_folder = "washingtonpost_images"
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
global_seen_images = set()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def download_image(image_url, idx):
    global image_count
    img_name = os.path.join(output_folder, f"image_{idx:03d}.jpg")
    if image_url in global_seen_images:
        logging.info(f"Skipping duplicate image: {image_url}")
        return
    try:
        logging.info(f"Attempting to download: {image_url} to {img_name}")
        response = requests.get(
            image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if response.status_code == 200 and 'image' in content_type.lower():
            with open(img_name, 'wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
            logging.info(f"Successfully downloaded {image_url}")
            image_count += 1
            global_seen_images.add(image_url)
        else:
            logging.warning(
                f"Skipped {image_url}: Status={response.status_code}, Type={content_type}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error downloading {image_url}: {e}")


def extract_and_download_from_page(url):
    try:
        logging.info(f"Visiting: {url}")
        driver.get(url)

        # Wait for page to load and check for images
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
            logging.info("Images detected on page")
        except TimeoutException:
            logging.error("Timeout waiting for images to load")
            return

        # Scroll to load all content
        last_height = driver.execute_script(
            "return document.body.scrollHeight")
        while True:
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # Increased wait for dynamic content
            new_height = driver.execute_script(
                "return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Log debugging info
        logging.info(f"Page title: {driver.title}")
        img_count = len(driver.find_elements(By.TAG_NAME, "img"))
        logging.info(f"Found {img_count} <img> elements")

        # Extract and download images
        images = driver.find_elements(By.TAG_NAME, "img")
        idx = image_count
        for img in images:
            try:
                # Check multiple attributes for image sources
                image_url = (img.get_attribute("src") or
                             img.get_attribute("data-src") or
                             img.get_attribute("data-lazy-src") or
                             img.get_attribute("data-original"))
                if image_url:
                    image_url = urljoin(url, image_url)
                    if image_url.startswith(('http://', 'https://')) and image_url not in global_seen_images:
                        logging.info(f"Found image URL: {image_url}")
                        download_image(image_url, idx)
                        idx += 1
            except Exception as e:
                logging.error(f"Error extracting image: {e}")

        # Extract links
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and base_url in href and href not in visited_urls and href not in urls_to_visit:
                    urls_to_visit.append(href)
            except Exception as e:
                logging.error(f"Error extracting link: {e}")

    except WebDriverException as e:
        logging.error(f"WebDriver error processing page {url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error processing page {url}: {e}")


# Crawl the website
max_pages = 50
with tqdm(total=max_pages, desc="Crawling pages") as pbar:
    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.popleft()
        if current_url not in visited_urls:
            visited_urls.add(current_url)
            extract_and_download_from_page(current_url)
            pbar.update(1)
            time.sleep(1)  # Rate limiting

driver.quit()
downloaded_files = [f for f in os.listdir(output_folder) if f.endswith('.jpg')]
logging.info(
    f"Process Complete! Found {len(downloaded_files)} images in '{output_folder}'")
print(f"✅ Done. {image_count} images downloaded to '{output_folder}'")
