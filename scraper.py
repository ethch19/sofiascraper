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
import exporter
import tkinter as tk
from tkinter import messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_URL = "https://medicine.sofia.imperial.ac.uk/map/a100/"
SIGNIN_URL = "https://login.microsoftonline.com/"

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

class LoginWindow(tk.Toplevel):
    def __init__(self, root):
        tk.Toplevel.__init__(self, root)
        self.title("Sign In")
        self.geometry("300x200")
        self.attributes('-topmost', True)
        self.grab_set()
        self.root = root
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        
    @classmethod
    def start_login(cls, root):
        self = cls(root)
        self.startup()

        if not self.is_signed_in():
            self.btn_clicked = tk.IntVar()
            self.create_widgets()
            self.await_login()
        else:
            self.after_login()

    def startup(self):
        self.server = Server("browsermob-proxy-2.1.4/bin/browsermob-proxy")
        self.server.start()
        self.proxy = self.server.create_proxy()
        self.proxy.new_har("microsoft_login", options={'captureHeaders': True, 'captureContent': True, 'trustAllServers': True})
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument(f"--proxy-server={self.proxy.proxy}")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        chrome_options.add_experimental_option("prefs", prefs)
        self.driver = ChromeWithPrefs(options=chrome_options)

    def is_signed_in(self):
        self.driver.get(TARGET_URL)
        time.sleep(1)  # Wait for the page to load
        return TARGET_URL in self.driver.current_url

    def verify_credentials(self):
        self.driver.get(SIGNIN_URL)
        WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.NAME, "loginfmt"))).send_keys(self.username_var.get() + Keys.RETURN)
        WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.NAME, "passwd"))).send_keys(self.password_var.get())
        time.sleep(5)
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "idSIButton9")))
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
            # Wait for the 2-step verification number to appear
            verification_number = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".displaySign"))
            ).text
            print(f"Please approve the sign-in request with the number: {verification_number}") #NEED A PROMPT OUT
            try:
                auth_sign = self.driver.find_element(By.CSS_SELECTOR, ".displaySign")
                return WebDriverWait(self.driver, 60).until(EC.staleness_of(auth_sign))
            except NoSuchElementException:
                return False
        except TimeoutException:
            print("No 2FA detected. Trying to head to sofia")
            return True

    def create_widgets(self):
        label_username = tk.Label(self, text="Username:")
        label_username.pack(pady=5)
        self.entry_username = tk.Entry(self, textvariable=self.username_var)
        self.entry_username.pack(pady=5)

        label_pw = tk.Label(self, text="Password:")
        label_pw.pack(pady=5)
        self.entry_password = tk.Entry(self, show="*", textvariable=self.password_var)
        self.entry_password.pack(pady=5)

        self.message = tk.Label(self, text="", fg="red")

        self.btn_login = tk.Button(self, text="Login", command=lambda: self.btn_clicked.set(1))
        self.btn_login.pack(pady=20)

    def on_login(self):
        print("Login verification triggered")
        if self.username_var.get() and self.password_var.get():
            answer = self.verify_credentials()
            print("completed verification")
            if answer:
                return True
        if self.message.winfo_exists():
            self.message.config(text="Please fill in both fields.")
        else:
            self.message.pack()
        return False
    
    def await_login(self):
        print(self.btn_clicked.get())
        self.btn_login.wait_variable(self.btn_clicked)
        if self.on_login():
            self.driver.get(TARGET_URL)
            self.after_login()
            return
        self.await_login()
        print("didn't wait")
    
    def after_login(self):
        self.destroy()
        print("Successful Sign-in: Scrapping has started")
        messagebox.showinfo("Login Successful", "Welcome!")
        time.sleep(5) # Can check the presence of loading icon
        monitor_traffic(self.proxy)
        self.driver.quit()
        self.server.stop()
        responses = exporter.get_responses()
        exporter.get_files(responses)

def clean_path(url):
    parsed_url = urlparse(url)
    path = parsed_url.path
    cleaned_path = os.path.basename(path)
    return cleaned_path

def monitor_traffic(proxy):
    # Save JSON responses from XHR/fetch requests
    dir_name = f"responses_{int(round(time.time()))}"
    save_dir = os.path.join(SCRIPT_DIR, dir_name)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    json_bool = True
    start_saving = "user"
    start_time = time.time()
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
                file_path = os.path.join(save_dir, file_name)
                with open(file_path, "w") as f:
                    f.write(content['text'])
    print(f"Elapsed Scraping Time: {time.time() - start_time} seconds")