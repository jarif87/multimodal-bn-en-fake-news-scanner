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
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize WebDriver with options
options = webdriver.ChromeOptions()
# Comment out headless for debugging
# options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')
options.add_argument('--disable-extensions')
try:
    driver = webdriver.Chrome(options=options)
    logging.info("WebDriver initialized successfully")
except Exception as e:
    logging.error(
        f"Failed to initialize WebDriver: {e}. Ensure ChromeDriver is installed.")
    exit(1)

base_url = "https://www.miamiherald.com/"
start_url = base_url

# Create folder to store images
output_folder = "miamiherald_images"
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

# Improved download function with better error handling


@retry(stop=stop_after_attempt(3),
       wait=wait_fixed(2),
       retry=retry_if_exception_type(requests.exceptions.RequestException))
def download_image(image_url, idx):
    global image_count
    # Skip small images (likely icons or thumbnails)
    if 'w=48&h=48' in image_url or 'w=32&h=32' in image_url:
        logging.info(f"Skipping small image: {image_url}")
        return

    # Clean URL - remove unneeded parameters
    clean_url = image_url.split('?')[0] if '?' in image_url else image_url

    # Set appropriate file extension based on URL
    file_ext = '.jpg'
    if '.png' in image_url.lower():
        file_ext = '.png'
    elif '.gif' in image_url.lower():
        file_ext = '.gif'
    elif '.webp' in image_url.lower():
        file_ext = '.webp'

    img_name = os.path.join(output_folder, f"image_{idx:03d}{file_ext}")

    if image_url in global_seen_images:
        logging.info(f"Skipping duplicate image: {image_url}")
        return

    try:
        logging.info(f"Downloading: {image_url}")
        # Reduced timeout to avoid long waits
        with requests.get(image_url, headers=headers, stream=True, timeout=8) as response:
            response.raise_for_status()
            content_type = response.headers.get('content-type', '')

            if 'image' in content_type.lower():
                with open(img_name, 'wb') as file:
                    # Larger chunks for efficiency
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)

                file_size = os.path.getsize(img_name)
                # Only keep reasonably sized images (5KB+)
                if file_size > 5000:
                    logging.info(
                        f"Downloaded {image_url} (Size: {file_size} bytes)")
                    image_count += 1
                    global_seen_images.add(image_url)
                else:
                    logging.warning(
                        f"Downloaded image too small ({file_size} bytes), removing")
                    os.remove(img_name)
            else:
                logging.warning(f"Not an image: {content_type}")
    except requests.exceptions.Timeout:
        logging.error(f"Timeout downloading {image_url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
    except OSError as e:
        logging.error(f"File error: {e}")


def extract_and_download_from_page(url):
    try:
        logging.info(f"Visiting: {url}")
        driver.get(url)

        # Wait for page to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
        except TimeoutException:
            logging.error("Timeout waiting for page to load")
            return

        # Simplified scrolling - just scroll once to load images
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Extract and download images
        img_elements = driver.find_elements(By.TAG_NAME, "img")
        logging.info(f"Found {len(img_elements)} images")

        idx = image_count
        for img in img_elements:
            try:
                # Check multiple attributes for image sources
                image_url = None
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'srcset']:
                    value = img.get_attribute(attr)
                    if value:
                        if attr == 'srcset':
                            # Get highest resolution from srcset
                            srcset_options = value.split(',')
                            if srcset_options:
                                image_url = srcset_options[-1].strip().split()[
                                    0]
                        else:
                            image_url = value
                        break

                if image_url:
                    # Make relative URLs absolute
                    image_url = urljoin(url, image_url)

                    # Only download http/https URLs
                    if image_url.startswith(('http://', 'https://')):
                        download_image(image_url, idx)
                        idx += 1
            except Exception as e:
                logging.error(f"Error processing image: {e}")

        # Extract links for crawling
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and href.startswith(base_url) and href not in visited_urls and href not in urls_to_visit:
                    urls_to_visit.append(href)
            except Exception as e:
                logging.error(f"Error extracting link: {e}")

    except WebDriverException as e:
        logging.error(f"WebDriver error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


# Main crawling loop
max_pages = 10  # Reduced for faster completion
with tqdm(total=max_pages, desc="Crawling pages") as pbar:
    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.popleft()
        if current_url not in visited_urls:
            visited_urls.add(current_url)
            extract_and_download_from_page(current_url)
            pbar.update(1)
            time.sleep(2)  # Allow some time between page visits

driver.quit()
downloaded_files = [f for f in os.listdir(
    output_folder) if os.path.isfile(os.path.join(output_folder, f))]
logging.info(
    f"Process Complete! Found {len(downloaded_files)} images in '{output_folder}'")
print(f"✅ Done. {image_count} images downloaded to '{output_folder}'")
