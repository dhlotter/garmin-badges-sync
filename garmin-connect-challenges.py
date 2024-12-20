#!/usr/bin/env python3

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import urllib3
import ssl
import platform
import sys
import subprocess
import tempfile
import shutil
import requests
from selenium.webdriver import ActionChains
import undetected_chromedriver as uc

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create an SSL context that doesn't verify certificates
ssl._create_default_https_context = ssl._create_unverified_context

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def get_system_info():
    """Get system OS and architecture information"""
    os_name = platform.system().lower()
    machine = platform.machine().lower()
    
    # Detect OS
    if os_name == 'darwin':
        system = 'mac'
    elif os_name == 'windows':
        system = 'windows'
    elif os_name == 'linux':
        system = 'linux'
    else:
        system = 'unknown'
    
    # Detect architecture
    is_arm = any(arm in machine for arm in ['arm', 'aarch'])
    is_64bit = sys.maxsize > 2**32
    
    arch = 'arm64' if is_arm and is_64bit else \
           'arm' if is_arm else \
           'x64' if is_64bit else \
           'x86'
    
    return system, arch

def get_chrome_version():
    """Get the installed Chrome version"""
    try:
        # On macOS, Chrome is typically installed here
        chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True)
        version = result.stdout.strip().split()[-1].split('.')[0]  # Get major version
        return version
    except Exception as e:
        logger.error(f"Failed to get Chrome version: {str(e)}")
        return None

def download_chromedriver(system, arch):
    """Download ChromeDriver based on system and architecture"""
    try:
        chrome_version = get_chrome_version()
        if not chrome_version:
            raise Exception("Could not determine Chrome version")
            
        logger.info(f"Chrome version: {chrome_version}")
        
        # Determine the correct download URL based on system and architecture
        if system == 'mac':
            if arch == 'arm64':
                platform_path = 'mac-arm64'
            else:
                platform_path = 'mac-x64'
        elif system == 'windows':
            platform_path = 'win64' if arch in ['x64', 'arm64'] else 'win32'
        else:  # linux
            platform_path = 'linux64'
            
        download_url = f"https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/{chrome_version}.0.6778.87/{platform_path}/chromedriver-{platform_path}.zip"
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "chromedriver.zip")
        
        # Download the file
        logger.info(f"Downloading ChromeDriver from {download_url}")
        response = requests.get(download_url, verify=False)
        response.raise_for_status()
        
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # Extract the zip file
        logger.info("Extracting ChromeDriver...")
        shutil.unpack_archive(zip_path, temp_dir)
        
        # Find the chromedriver binary
        chromedriver_path = None
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file == 'chromedriver' or file == 'chromedriver.exe':
                    chromedriver_path = os.path.join(root, file)
                    break
            if chromedriver_path:
                break
                
        if not chromedriver_path:
            raise Exception("ChromeDriver binary not found in downloaded package")
            
        # Make it executable
        os.chmod(chromedriver_path, 0o755)
        
        return chromedriver_path
        
    except Exception as e:
        logger.error(f"Failed to download ChromeDriver: {str(e)}")
        raise

def setup_driver(headless=True):
    """Setup Chrome driver with appropriate options"""
    try:
        # Use undetected-chromedriver options
        options = uc.ChromeOptions()
        
        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--use-fake-ui-for-media-stream')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--no-first-run')
            options.add_argument('--no-service-autorun')
            options.add_argument('--password-store=basic')
            options.add_argument('--lang=en-US')
            
            # Set user agent
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Create undetected Chrome driver
        driver = uc.Chrome(
            options=options,
            headless=headless,
        )
        
        if headless:
            # Additional JavaScript patches for headless mode
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # Modify navigator.webdriver flag
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Add additional properties to make headless more stealthy
            driver.execute_script("""
                // Overwrite the 'navigator' property to include common plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Add language preferences
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Add a fake notification API
                window.Notification = {
                    permission: 'default',
                    requestPermission: async () => 'default'
                };
            """)
        
        return driver
        
    except Exception as e:
        logger.error(f"Failed to setup driver: {str(e)}")
        raise

def check_cloudflare(driver, url):
    """Check if Cloudflare verification is needed"""
    try:
        driver.get(url)
        time.sleep(2)
        
        # Check for Cloudflare elements
        cloudflare_elements = driver.find_elements(By.ID, "challenge-stage")
        if cloudflare_elements:
            logger.info("Cloudflare verification detected")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking Cloudflare: {str(e)}")
        return False

def login_to_garmin(driver, email, password):
    """Login to Garmin Connect"""
    try:
        logger.info("Attempting to log in to Garmin Connect...")
        
        # Go directly to the SSO sign-in page with the correct parameters
        login_url = "https://sso.garmin.com/portal/sso/en-US/sign-in?clientId=GarminConnect&service=https%3A%2F%2Fconnect.garmin.com%2Fmodern"
        driver.get(login_url)
        
        # Wait for potential Cloudflare check
        logger.info("Waiting for page to be ready (including potential Cloudflare verification)...")
        
        # Wait for login form to be fully loaded and interactive
        logger.info("Waiting for login form to be ready...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.NAME, "email"))
        )
        time.sleep(2)  # Additional wait for any animations
        
        logger.info("Entering credentials...")
        
        # Wait for and fill in email
        logger.info("Waiting for email field...")
        email_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        logger.info("Found email field, entering email...")
        email_field.clear()
        email_field.send_keys(email)
        time.sleep(1)
        
        # Fill in password
        logger.info("Waiting for password field...")
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        logger.info("Found password field, entering password...")
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(1)
        
        # Click the button
        logger.info("Looking for sign in button...")
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        logger.info("Found sign in button, clicking...")
        
        # Try multiple click methods for the submit button
        try:
            # Try JavaScript click first
            driver.execute_script("arguments[0].click();", submit_button)
        except:
            try:
                # Try regular click
                submit_button.click()
            except:
                # Try moving to element first
                actions = ActionChains(driver)
                actions.move_to_element(submit_button).click().perform()
        
        # Wait for redirect to modern interface
        logger.info("Waiting for redirect to Garmin Connect...")
        try:
            # First wait for URL change
            WebDriverWait(driver, 45).until(
                lambda x: x.current_url != login_url
            )
            logger.info(f"URL changed to: {driver.current_url}")
            
            # Then wait for final redirect
            WebDriverWait(driver, 45).until(
                lambda x: "connect.garmin.com/modern" in x.current_url
            )
            logger.info(f"Final URL: {driver.current_url}")
            
            # Wait for login to fully complete
            logger.info("Waiting for login to fully complete...")
            time.sleep(5)
            
            # Navigate directly to challenges page
            logger.info("Navigating to challenges page...")
            driver.get("https://connect.garmin.com/modern/challenge")
            
            return True
            
        except Exception as e:
            # Take screenshot
            screenshot_path = "login_error.png"
            driver.save_screenshot(screenshot_path)
            logger.error(f"Screenshot saved to {screenshot_path}")
            
            # Try to find error messages
            try:
                error_messages = driver.find_elements(By.CLASS_NAME, "error-message")
                for msg in error_messages:
                    logger.error(f"Error message found: {msg.text}")
            except:
                pass
                
            try:
                error_messages = driver.find_elements(By.CLASS_NAME, "alert-danger")
                for msg in error_messages:
                    logger.error(f"Alert message found: {msg.text}")
            except:
                pass
            
            raise
            
    except Exception as e:
        logger.error(f"Failed to log in: {str(e)}")
        if hasattr(e, '__cause__') and e.__cause__:
            logger.error(f"Caused by: {str(e.__cause__)}")
        return False

def wait_for_challenges_page(driver):
    """Wait for the challenges page to load"""
    try:
        logger.info("Waiting for challenges page to load...")
        
        # Wait for either the challenge cards or a join button to appear
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'BadgeChallengeCard')]")),
                EC.presence_of_element_located((By.XPATH, "//button[text()='Join']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='badge-challenge-card']"))
            )
        )
        
        # Wait a bit more for all dynamic content
        time.sleep(5)
        return True
        
    except Exception as e:
        logger.error(f"Failed to load challenges page: {str(e)}")
        return False

def join_challenges(driver):
    """Join all available challenges"""
    try:
        print("\n=== Navigating to Challenges Page ===")
        driver.get("https://connect.garmin.com/modern/challenge")
        
        if not wait_for_challenges_page(driver):
            logger.error("Could not load challenges page")
            return
        
        # Wait a bit more for dynamic content
        time.sleep(5)
        
        # Find all Join buttons
        join_buttons = driver.find_elements(By.XPATH, "//button[text()='Join']")
        total_challenges = len(join_buttons)
        
        if total_challenges == 0:
            print("\n✨ No new challenges found to join!")
            return
            
        print(f"\n=== Found {total_challenges} Challenge{'s' if total_challenges > 1 else ''} to Join ===")
        
        challenges_joined = 0
        for button in join_buttons:
            try:
                # Get the challenge name from the card using a more robust selector
                try:
                    # Find the parent card element
                    challenge_card = button.find_element(By.XPATH, "./ancestor::div[contains(@class, 'BadgeChallengeCard')]")
                    
                    # Try multiple selectors for the name
                    name_selectors = [
                        ".//div[contains(@class, 'badgeName')]",  # Generic class name
                        ".//div[contains(@class, 'BadgeChallengeCard') and contains(@class, 'badgeName')]",  # More specific
                        ".//div[contains(@class, 'title')]",  # Fallback to generic title
                        ".//div[contains(@class, 'name')]",  # Another fallback
                    ]
                    
                    challenge_name = None
                    for selector in name_selectors:
                        try:
                            name_elem = challenge_card.find_element(By.XPATH, selector)
                            challenge_name = name_elem.text
                            if challenge_name:
                                break
                        except:
                            continue
                    
                    if not challenge_name:
                        challenge_name = "Unknown Challenge"
                        
                except Exception as e:
                    logger.debug(f"Could not get challenge details: {str(e)}")
                    challenge_name = "Unknown Challenge"
                
                print(f"\n🎯 Joining challenge ({challenges_joined + 1}/{total_challenges}): {challenge_name}")
                
                # Scroll the button into view with offset to avoid header overlap
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(1)  # Wait for any animations
                
                # Try multiple click methods
                try:
                    # Try JavaScript click first
                    driver.execute_script("arguments[0].click();", button)
                except:
                    try:
                        # Try regular click
                        button.click()
                    except:
                        # Try moving to element first
                        actions = ActionChains(driver)
                        actions.move_to_element(button).click().perform()
                
                challenges_joined += 1
                print(f"✅ Successfully joined: {challenge_name}")
                time.sleep(2)  # Wait between joins
                
            except Exception as e:
                print(f"❌ Failed to join: {challenge_name}")
                logger.error(f"Error details: {str(e)}")
                # Try to scroll past this button and continue
                driver.execute_script("window.scrollBy(0, 100);")
                continue
        
        print(f"\n=== Summary ===")
        print(f"✨ Successfully joined {challenges_joined} out of {total_challenges} challenge{'s' if total_challenges > 1 else ''}")
        if challenges_joined < total_challenges:
            print(f"⚠️  Failed to join {total_challenges - challenges_joined} challenge{'s' if (total_challenges - challenges_joined) > 1 else ''}")
        
        return challenges_joined
        
    except Exception as e:
        logger.error(f"Error in join_challenges: {str(e)}")
        return 0

def main():
    """Main function"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get credentials from environment variables
        email = os.getenv("GARMIN_CONNECT_USERNAME")
        password = os.getenv("GARMIN_CONNECT_PASSWORD")
        
        if not email or not password:
            print("❌ Error: Missing Garmin Connect credentials")
            print("Please set GARMIN_CONNECT_USERNAME and GARMIN_CONNECT_PASSWORD environment variables")
            return
        
        print("\n=== Starting Garmin Challenge Joiner ===")
        print("🔄 Initializing browser in headless mode...")
        driver = setup_driver(headless=True)
        
        try:
            print("\n=== Logging in to Garmin Connect ===")
            if not login_to_garmin(driver, email, password):
                print("❌ Failed to log in to Garmin Connect")
                return
                
            # Join challenges
            join_challenges(driver)
            
        except Exception as e:
            print(f"\n❌ Script failed: {str(e)}")
        finally:
            # Always close the browser
            try:
                driver.quit()
            except:
                pass
            
    except Exception as e:
        print(f"\n❌ Script failed: {str(e)}")

if __name__ == "__main__":
    main()