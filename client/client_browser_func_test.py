from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from chrome_setup import CHROMEDRIVER_PATH, build_chrome_options

# Basic test for selenium
# Run in termux shell

options = build_chrome_options()
driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
driver.get("https://archlinux.org")
driver.save_screenshot("./screenshot.png")
driver.quit()
