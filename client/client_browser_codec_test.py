from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from chrome_setup import CHROMEDRIVER_PATH, build_chrome_options

# Check device codec support
# Run in termux shell

options = build_chrome_options(autoplay=True)
driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

codec_support = driver.execute_script(
    """
    return {
      h264: MediaSource.isTypeSupported('video/mp4; codecs="avc1.640028"'),
      av1:  MediaSource.isTypeSupported('video/mp4; codecs="av01.0.08M.08"'),
      hevc: MediaSource.isTypeSupported('video/mp4; codecs="hvc1.1.6.L93.B0"'),
      hvc: MediaSource.isTypeSupported('video/mp4; codecs="hvc1.1.6.L93.B0"')
    };
"""
)
print(codec_support)

driver.quit()
