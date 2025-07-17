import time
import json
import datetime
import re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bing_image_downloader.data_model import ImageData

class BingImageScraper:
    def __init__(self, debug=False):
        self.debug = debug
        options = Options()
        options.add_argument("-headless")
        options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Firefox(options=options)
        self.scraped_image_ids = set()

    def __del__(self):
        self.driver.quit()

    def search(self, query: str):
        if self.driver:
            self.driver.quit()
        options = Options()
        options.add_argument("-headless")
        options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Firefox(options=options)
        self.scraped_image_ids = set()

        start_time = time.perf_counter()
        self.driver.get(f"https://www.bing.com/images/search?q={query}")
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//li[@data-idx]"))
            )
            self._clean_page_overlays() # Clean overlays after initial load
        except TimeoutException:
            print("Initial image results did not load.")
            return []
        end_time = time.perf_counter()
        print(f"Search and initial page load took: {end_time - start_time:.2f} seconds")

    def _clean_page_overlays(self):
        """Attempts to dismiss common page-level overlays like cookie banners or sign-in prompts."""
        print("Attempting to clean page overlays...")
        # Try to dismiss cookie consent banner
        try:
            cookie_accept_button = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.ID, "bnp_btn_accept"))
            )
            cookie_accept_button.click()
            WebDriverWait(self.driver, 3).until(
                EC.invisibility_of_element_located((By.ID, "bnp_container"))
            )
            print("Cookie banner dismissed.")
        except TimeoutException:
            print("No cookie banner found or dismissed.")
            pass
        except WebDriverException as e:
            print(f"Error dismissing cookie banner: {e}")
            pass

        # Try to dismiss any general pop-ups by pressing ESC
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            print("Sent ESC key to dismiss potential pop-ups.")
            time.sleep(0.5) # Give a moment for any pop-up to react
        except WebDriverException as e:
            print(f"Error sending ESC key: {e}")
            pass

    def get_image_data(self, max_images: int = 100, scroll_pause_time: int = 2) -> list[ImageData]:
        """Gets all the image data from the current search results page."""
        total_start_time = time.perf_counter()
        newly_scraped_images = []

        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while len(newly_scraped_images) < max_images:
            li_elements = self.driver.find_elements(By.XPATH, "//li[@data-idx]")

            for element in li_elements:
                data_idx = element.get_attribute("data-idx")
                if data_idx and data_idx not in self.scraped_image_ids:
                    self.scraped_image_ids.add(data_idx)
                    image_data = None # Initialize image_data
                    try:
                        parse_start_time = time.perf_counter()
                        m_attr = element.find_element(By.TAG_NAME, "a").get_attribute("m")
                        if m_attr:
                            m_data = json.loads(m_attr)
                            image_data = self._parse_image_data(m_data, data_idx, element)
                            if self.debug:
                                print(f"[DEBUG] Scraped data for image {data_idx}: {image_data}")
                            
                            # Get thumbnail
                            try:
                                thumb_element = element.find_element(By.TAG_NAME, "img")
                                if self.debug:
                                    print(f"[DEBUG] Attempting screenshot for {image_data.title}")
                                image_data.thumbnail = thumb_element.screenshot_as_png
                                if self.debug and image_data.thumbnail:
                                    print(f"[DEBUG] Screenshot successful for {image_data.title}, size: {len(image_data.thumbnail)} bytes")
                                elif self.debug and not image_data.thumbnail:
                                    print(f"[DEBUG] Screenshot returned None for {image_data.title}")
                            except (NoSuchElementException, WebDriverException) as e:
                                if self.debug:
                                    print(f"[DEBUG] Error taking screenshot for {image_data.title}: {e}")
                                image_data.thumbnail = None

                            newly_scraped_images.append(image_data)
                            if len(newly_scraped_images) >= max_images:
                                break
                            parse_end_time = time.perf_counter()
                            print(f"  Parsing and thumbnail for {image_data.title} took: {parse_end_time - parse_start_time:.2f} seconds")
                    except (NoSuchElementException, json.JSONDecodeError) as e:
                        print(f"Could not extract data for image {data_idx}: {e}")

            if len(newly_scraped_images) >= max_images:
                break

            scroll_start_time = time.perf_counter()
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("No new content loaded after scrolling.")
                break
            last_height = new_height
            scroll_end_time = time.perf_counter()
            print(f"  Scrolling took: {scroll_end_time - scroll_start_time:.2f} seconds")

        total_end_time = time.perf_counter()
        print(f"Total get_image_data took: {total_end_time - total_start_time:.2f} seconds for {len(newly_scraped_images)} images")
        return newly_scraped_images

    def _parse_image_data(self, m_data: dict, data_idx: str, li_element) -> ImageData:
        info = ImageData()
        info.data_idx = data_idx
        info.title = m_data.get("t")
        info.image_source_url = m_data.get("murl")

        purl = m_data.get("purl")
        if purl:
            parsed_uri = urlparse(purl)
            info.site_source = parsed_uri.netloc

        width = m_data.get("w")
        height = m_data.get("h")
        if width and height:
            info.size = f"{width} x {height}"
        else:
            # Fallback to 's' if width/height not present, and try to parse it
            size_str = m_data.get("s")
            if size_str:
                match = re.search(r'(\d+) x (\d+)', size_str)
                if match:
                    info.size = f"{match.group(1)} x {match.group(2)}"
                else:
                    info.size = size_str # Keep original string if parsing fails
            if self.debug:
                print(f"[DEBUG] Extracted size for {info.title}: {info.size}")

        info.file_type = m_data.get("f")

        try:
            ago_element = li_element.find_element(By.CSS_SELECTOR, ".ppdatr")
            info.age = ago_element.text
            if info.age:
                match = re.search(r'(\d+)\s+(day|week|month|year)s?', info.age)
                if match:
                    value = int(match.group(1))
                    unit = match.group(2)
                    if unit == 'day': info.parsed_age = value
                    elif unit == 'week': info.parsed_age = value * 7
                    elif unit == 'month': info.parsed_age = value * 30
                    elif unit == 'year': info.parsed_age = value * 365

            tooltip_date = ago_element.get_attribute("title")
            if tooltip_date:
                try:
                    info.parsed_date = datetime.datetime.strptime(tooltip_date, '%m/%d/%Y').date()
                    info.date = tooltip_date
                except ValueError:
                    pass
        except NoSuchElementException:
            pass

        return info

    def get_detailed_info(self, data: ImageData) -> ImageData:
        if self.debug:
            print(f"[DEBUG] Getting detailed info for: {data.title}")
        try:
            # Ensure we are in the default content before clicking
            self.driver.switch_to.default_content()

            # Find the element to click
            element_to_click = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//li[@data-idx='{data.data_idx}']//a"))
            )
            # Scroll the element into view if it's not already
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element_to_click)
            if self.debug:
                print(f"[DEBUG] Clicking element: {element_to_click}")
            element_to_click.click()

            # Switch to the pop-over frame
            try:
                if self.debug:
                    print("[DEBUG] Switching to iframe...")
                WebDriverWait(self.driver, 10).until(
                    EC.frame_to_be_available_and_switch_to_it(0) # Assuming the iframe is the first one
                )
                if self.debug:
                    print("[DEBUG] Switched to iframe.")
            except TimeoutException:
                if self.debug:
                    print("[DEBUG] Could not find iframe by index 0.")
                raise # Re-raise to be caught by outer except

            # Add any other detailed info extraction here if needed
            # For now, this method primarily handles the click and frame switching.

            # Switch back to default content
            if self.debug:
                print("[DEBUG] Switching back to default content...")
            self.driver.switch_to.default_content()
            if self.debug:
                print("[DEBUG] Switched back to default content.")
            
            # Try to close the pop-over on the default content
            try:
                if self.debug:
                    print("[DEBUG] Closing pop-over...")
                close_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".img_info_close"))
                )
                close_button.click()
                if self.debug:
                    print("[DEBUG] Closed pop-over.")
            except (NoSuchElementException, TimeoutException):
                # Fallback: Try pressing ESC on the main page
                if self.debug:
                    print("[DEBUG] Pop-over close button not found, sending ESC key.")
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5) # Small delay after closing

        except (NoSuchElementException, TimeoutException, WebDriverException) as e:
            if self.debug:
                print(f"[DEBUG] Could not get detailed info for {data.title}: {e}")
            try:
                self.driver.switch_to.default_content() # Always switch back in case of error
            except WebDriverException:
                pass # Already in default content or driver is gone
        
        return data