from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# Basic test for selenium
# Run in termux shell

CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"

options = webdriver.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
driver.get("https://archlinux.org")
driver.save_screenshot("./screenshot.png")
driver.quit()
