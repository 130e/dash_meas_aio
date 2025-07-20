from selenium import webdriver

# Basic test for selenium
# Run in termux shell

options = webdriver.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)
driver.get("https://archlinux.org")
driver.save_screenshot("~/storage/downloads/screenshot.png")
driver.quit()
