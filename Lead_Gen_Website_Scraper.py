import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin
from keybert import KeyBERT

def get_sheet_data(sheet_id, tab_name, api_key):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab_name}?key={api_key}"
    response = requests.get(url)
    data = response.json()

    headers = data["values"][0]
    rows = data["values"][1:]

    lead_list = []
    for row in rows:
        if len(row) < len(headers):
            row += [''] * (len(headers) - len(row))
        lead_list.append(dict(zip(headers, row)))

    return lead_list

def extract_website(lead):
    if "WEBSITE" in lead:
        url = lead["WEBSITE"].strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        return url

    for key in lead:
        if "website" in key.lower() or "url" in key.lower():
            url = lead[key].strip()
            if url and not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            return url
    return None

def find_about_page_selenium(driver, base_url):
    try:
        driver.get(base_url)
        time.sleep(3)
        links = driver.find_elements(By.TAG_NAME, "a")
        candidates = []

        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.lower()
                href_lower = href.lower()

                score = 0
                if "about" in href_lower or "about" in text:
                    score += 3
                if any(x in href_lower for x in ["our-story", "company", "team", "who-we-are"]):
                    score += 2
                if any(x in text for x in ["our story", "company", "team", "who we are"]):
                    score += 2

                if score > 0:
                    candidates.append((score, href))
            except:
                continue

        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0][1]
    except Exception as e:
        print(f"[Selenium error on {base_url}]: {e}")
        return None

def scrape_text(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        print(f"[Error scraping {url}]: {e}")
        return ""

def extract_keywords(text, top_n=10):
    kw_model = KeyBERT()
    keywords = kw_model.extract_keywords(text, keyphrase_ngram_range=(1, 2), stop_words="english")
    return [kw[0] for kw in keywords[:top_n]]

def generate_content(brand, keywords):
    if not keywords:
        return f"{brand} has a unique presence in its industry."
    return f"{brand} focuses on {', '.join(keywords[:5])}, aiming to provide value and impact in its niche."

if __name__ == "__main__":
    sheet_id = "sheet_id"                                       # place your google sheet id here
    tab_name = "Sheet1"                                         # place your tab name here(eg. sheet1)
    api_key = "google_sheet_api_key"                            # place the google sheets api key here

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    leads = get_sheet_data(sheet_id, tab_name, api_key)
    print(f"Loaded {len(leads)} leads.\n")

    for lead in leads[:2]:  
        brand = lead.get("COMPANY NAME") or lead.get("Brand Name") or "Unnamed Brand"
        website = extract_website(lead)

        if not website:
            print(f"No website found for {brand}. Skipping.")
            continue

        print(f"\n Processing {brand} ({website})...")
        about_url = find_about_page_selenium(driver, website)

        if not about_url:
            print("Couldn't find About page.")
            continue

        print(f"About page found: {about_url}")
        about_text = scrape_text(about_url)

        if not about_text or len(about_text.split()) < 30:
            print("Not enough content extracted.")
            continue

        keywords = extract_keywords(about_text)
        content = generate_content(brand, keywords)
        print(f"Generated Content:\n{content}\n")

    driver.quit()