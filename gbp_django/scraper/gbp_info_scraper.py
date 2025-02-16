#!/usr/bin/env python3
"""
GBP Info Scraper: Attempts to retrieve a Google Business Profile (GBP) page using a direct HTTP request.
Falls back to Selenium if dynamic content is missing. Collects business details, hours, menus, photos,
reviews, posts, promos, locations, and SEO data.
NOTE: Adjust CSS selectors as needed based on your GBP page’s structure.
"""

import time
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def fetch_using_requests(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
                      "AppleWebKit/537.36 (KHTML, like Gecko) " +
                      "Chrome/110.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"[SCRAPER] Requests error: {e}")
    return None

def init_selenium_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # Update driver path as needed
    driver_path = "/path/to/chromedriver"
    driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options)
    return driver

def fetch_using_selenium(url):
    driver = init_selenium_driver()
    driver.get(url)
    # Allow time for dynamic content to load
    time.sleep(5)
    # Scroll to load dynamic sections if necessary
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    page_source = driver.page_source
    driver.quit()
    return page_source

def parse_gbp_page(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    
    # Extract Business Name (adjust selector as needed)
    try:
        data['name'] = soup.find("h1", class_="section-hero-header-title").get_text(strip=True)
    except Exception:
        data['name'] = None

    # Extract Business Hours (example selector; may need adjustment)
    hours = []
    try:
        hours_table = soup.find("table", class_="section-open-hours-table")
        if hours_table:
            for row in hours_table.find_all("tr"):
                day = row.find("td", class_="section-open-hours-day").get_text(strip=True)
                timing = row.find("td", class_="section-open-hours-time").get_text(strip=True)
                hours.append({"day": day, "time": timing})
    except Exception:
        hours = None
    data['hours'] = hours

    # Extract Reviews (basic extraction; pagination may be required)
    reviews = []
    try:
        for review in soup.find_all("div", class_="section-review-text"):
            reviews.append(review.get_text(strip=True))
    except Exception:
        reviews = None
    data['reviews'] = reviews

    # Placeholders for additional sections
    data['menus'] = "Extract menu details using custom selectors."
    data['photos'] = "Extract photo URLs using custom selectors."
    data['posts'] = "Extract posts using custom selectors."
    data['promos'] = "Extract promotional information using custom selectors."
    data['locations'] = "Extract additional location data if present."
    data['seo_data'] = "Extract SEO metadata and structured data."

    return data

def scrape_gbp_profile(business_url):
    print("[SCRAPER] Attempting direct HTTP request...")
    html = fetch_using_requests(business_url)
    # Check for key element that indicates dynamic content is loaded (e.g., business name)
    if html:
        soup = BeautifulSoup(html, "html.parser")
        if soup.find("h1", class_="section-hero-header-title") is None:
            print("[SCRAPER] Dynamic content missing. Falling back to Selenium retrieval.")
            html = fetch_using_selenium(business_url)
    else:
        print("[SCRAPER] HTTP request failed. Using Selenium fallback.")
        html = fetch_using_selenium(business_url)
        
    data = parse_gbp_page(html)
    return data

if __name__ == "__main__":
    # Replace with the actual Google Business Profile URL of the business
    gbp_url = "https://www.google.com/maps/place/YourBusinessURL"
    scraped_data = scrape_gbp_profile(gbp_url)
    print(json.dumps(scraped_data, indent=4))
