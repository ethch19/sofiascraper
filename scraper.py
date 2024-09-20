import os
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from browsermobproxy import Server
from functools import reduce
import undetected_chromedriver as uc
from urllib.parse import urlparse
import json
import time

class ChromeWithPrefs(uc.Chrome):
    def __init__(self, *args, options=None, **kwargs):
        if options:
            self._handle_prefs(options)

        super().__init__(*args, options=options, **kwargs)

        # remove the user_data_dir when quitting
        self.keep_user_data_dir = False

    @staticmethod
    def _handle_prefs(options):
        if prefs := options.experimental_options.get("prefs"):
            # turn a (dotted key, value) into a proper nested dict
            def undot_key(key, value):
                if "." in key:
                    key, rest = key.split(".", 1)
                    value = undot_key(rest, value)
                return {key: value}

            # undot prefs dict keys
            undot_prefs = reduce(
                lambda d1, d2: {**d1, **d2},  # merge dicts
                (undot_key(key, value) for key, value in prefs.items()),
            )

            # create an user_data_dir and add its path to the options
            user_data_dir = os.path.normpath(tempfile.mkdtemp())
            options.add_argument(f"--user-data-dir={user_data_dir}")

            # create the preferences json file in its default directory
            default_dir = os.path.join(user_data_dir, "Default")
            os.mkdir(default_dir)

            prefs_file = os.path.join(default_dir, "Preferences")
            with open(prefs_file, encoding="latin1", mode="w") as f:
                json.dump(undot_prefs, f)

            # pylint: disable=protected-access
            # remove the experimental_options to avoid an error
            del options._experimental_options["prefs"]


script_dir = os.path.dirname(os.path.abspath(__file__))

# Start BrowserMob Proxy
server = Server("browsermob-proxy-2.1.4/bin/browsermob-proxy")
server.start()
proxy = server.create_proxy()

# Set up proxy to capture network traffic
proxy.new_har("microsoft_login", options={'captureHeaders': True, 'captureContent': True, 'trustAllServers': True})

# Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument(f"--proxy-server={proxy.proxy}")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
prefs = {
    "credentials_enable_service": False,
    "profile.password_manager_enabled": False
}
chrome_options.add_experimental_option("prefs", prefs)

driver = ChromeWithPrefs(options=chrome_options)

def is_signed_in(driver, target_url):
    driver.get(target_url)
    time.sleep(1)  # Wait for the page to load
    return target_url in driver.current_url

def get_user_pw():
    username = input("Enter your username: ")
    password = input("Enter your password: ")
    return username, password

def verify_credentials(driver, username, password):
    driver.get("https://login.microsoftonline.com/")
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "loginfmt"))).send_keys(username + Keys.RETURN)
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "passwd"))).send_keys(password)
    time.sleep(1)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "idSIButton9")))
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
        # Wait for the 2-step verification number to appear
        verification_number = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".displaySign"))
        ).text
        print(f"Please approve the sign-in request with the number: {verification_number}")
        try:
            auth_sign = driver.find_element(By.CSS_SELECTOR, ".displaySign")
            return WebDriverWait(driver, 60).until(EC.staleness_of(auth_sign))
        except NoSuchElementException:
            return False
    except TimeoutException:
        print("No 2FA detected. Trying to head to sofia")
        return True

def clean_path(url):
    parsed_url = urlparse(url)
    path = parsed_url.path
    cleaned_path = os.path.basename(path)
    return cleaned_path

target_url = "https://medicine.sofia.imperial.ac.uk/map/a100/"

if not is_signed_in(driver, target_url):
    while True:
        username, password = get_user_pw()
        if verify_credentials(driver, username, password):
            break
        else:
            print("Invalid credentials or MFA failed. Please try again")
    # Navigate to the target page
    driver.get(target_url)


print("Successful Sign-in: Scrapping has started")

start_time = time.time()
# Wait for the page to load and capture network traffic
time.sleep(5) # Can check the presence of loading icon

# Save JSON responses from XHR/fetch requests
dir_name = f"responses_{int(round(time.time()))}"
save_dir = os.path.join(script_dir, dir_name)
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

json_bool = input("Scan only .json files? (Y/N): ")
while not(json_bool == "Y" or json_bool == "N"):
    print("Invalid input, try again.")
    json_bool = input("Scan only .json files? (Y/N): ")
json_bool = True if json_bool == 'Y' else False

start_saving = "user"

for entry in proxy.har['log']['entries']:
    request = entry['request']
    response = entry['response']
    content = response['content']
    name = clean_path(request['url'])
    if json_bool:
        if "application/json" in response['content']['mimeType']:
            if not (start_saving == True or name == start_saving):
                continue
            else:
                start_saving = True
            print(name)
            if 'text' in content:
                if not len(content['text']):
                    continue
                file_path = os.path.join(save_dir, f"{int(round(time.time_ns()))}_{name}.json")
                with open(file_path, "w") as f:
                    json_obj = json.loads(content['text'])
                    json.dump(json_obj, f, indent=4)
    else:
        if 'text' in content:
            if not len(content['text']):
                continue
            file_name = f"{name}_response_{int(round(time.time() * 1000))}.txt"
            print(content['mimeType'])
            print(file_name)
            file_path = os.path.join(save_dir, file_name)
            with open(file_path, "w") as f:
                f.write(content['text'])

print(f"Elapsed Scraping Time: {time.time() - start_time} seconds")

# Clean up
driver.quit()
server.stop()
print(f"Processes Terminated")