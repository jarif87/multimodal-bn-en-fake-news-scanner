import os
import time
import requests
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Initialize WebDriver
driver = webdriver.Chrome()
url = "https://www.jugantor.com/"

# Create folder to store images
os.makedirs("real_images", exist_ok=True)

# Open the website
driver.get(url)
time.sleep(3)  # Allow initial page load

# Scroll multiple times to load more images
for _ in range(15):  # Adjust scrolling limit if needed
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
    time.sleep(2)  # Allow time for images to load

# Find all image elements
images = driver.find_elements(By.TAG_NAME, "img")

image_urls = set()  # Use a set to store unique image URLs

for img in tqdm(images):
    try:
        image_url = img.get_attribute("src")
        if image_url and "http" in image_url:  # Ensure it's a valid URL
            image_urls.add(image_url)  # Store unique images
    except Exception as e:
        print(f"Error extracting image: {e}")

# Close the browser
driver.quit()

# Download images
for idx, image_url in enumerate(tqdm(image_urls)):
    try:
        img_name = f"real_images/image_{idx}.jpg"
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            with open(img_name, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
    except Exception as e:
        print(f"Error downloading {image_url}: {e}")

print("✅ Download Completed! All images saved in 'real_images/'")
