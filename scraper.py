import os
import tempfile
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from browsermobproxy import Server
from functools import reduce
import undetected_chromedriver as uc
from urllib.parse import urlparse
import json
import time
import exporter
import tkinter as tk
import tkinter.ttk as ttk
from concurrent import futures
import sys

TARGET_URL = "https://medicine.sofia.imperial.ac.uk/map/a100/"
SIGNIN_URL = "https://login.microsoftonline.com/"

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

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

def startup():
    print("Startup triggered")
    server = Server(os.path.join(base_path, "browsermob-proxy-2.1.4/bin/browsermob-proxy"))
    server.start()
    proxy = server.create_proxy()
    proxy.new_har("microsoft_login", options={'captureHeaders': True, 'captureContent': True, 'trustAllServers': True})
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
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
    driver.get(TARGET_URL)
    time.sleep(1)
    status = TARGET_URL in driver.current_url
    print("Startup completed")
    return {"server": server, "proxy": proxy, "driver": driver, "status": status}

def verify_credentials(driver, message, username, password):
    driver.get(SIGNIN_URL)
    print("Verifying credentials")
    username = username + "@ic.ac.uk"
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "loginfmt"))).send_keys(username + Keys.RETURN)
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "passwd"))).send_keys(password)
    time.sleep(1)
    try:
        attempts = 0
        while attempts < 2:
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "idSIButton9")))
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
                break
            except StaleElementReferenceException:
                attempts += 1
        # Wait for the 2-step verification number to appear
        verification_number = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".displaySign"))).text
        while verification_number == "" or verification_number is None:
            time.sleep(0.1)
            verification_number = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".displaySign"))).text
        number_text = f"2FA number: {verification_number}"
        message.config(text=number_text, fg="#4d6b0c")
        try:
            attempts = 0
            while attempts < 2:
                try:
                    time.sleep(0.5)
                    auth_sign = driver.find_element(By.CSS_SELECTOR, ".displaySign")
                    return WebDriverWait(driver, 60).until(EC.staleness_of(auth_sign))
                except:
                    attempts += 1
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

def monitor_traffic(driver, proxy):
    driver.get(TARGET_URL)
    time.sleep(1)
    WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".Loader")))
    # Save JSON responses from XHR/fetch requests
    dir_name = f"responses_{int(round(time.time()))}"
    save_dir = os.path.join(base_path, dir_name)
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

class LoginWindow(tk.Toplevel):
    def __init__(self, root):
        tk.Toplevel.__init__(self, root)
        self.executor = futures.ThreadPoolExecutor(max_workers=2)
        self.webscraper_thread = self.executor.submit(startup)
        self.webscraper_thread.add_done_callback(self.startup_callback)
        self.title("Sign In")
        self.geometry("400x350")
        self.attributes('-topmost', True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.root = root
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.logged_in = False
        self.verifying = False
        self.protocol("WM_DELETE_WINDOW", self.force_end)
        self.transient(root)
        self.grab_set()

    @classmethod
    def start_login(cls, root, callback, mainwindow_callback):
        self = cls(root)

        self.callback = callback
        self.mainwindow_callback = mainwindow_callback
        self.btn_clicked = tk.IntVar()
        self.create_widgets()
        self.await_login()

    def create_widgets(self):
        self.frame = ttk.Frame(self, padding="10 10 10 10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=3)
        self.frame.rowconfigure(2, weight=1)

        label_username = tk.Label(self.frame, text="Shortcode:")
        label_username.grid(column=0, row=0, padx=5, pady=5, sticky="NSW")
        self.entry_username = tk.Entry(self.frame, textvariable=self.username_var)
        self.entry_username.grid(column=1, row=0, padx=5, pady=5, sticky="NSWE")

        label_pw = tk.Label(self.frame, text="Password:")
        label_pw.grid(column=0, row=1, padx=5, pady=5, sticky="NSW")
        self.entry_password = tk.Entry(self.frame, show="*", textvariable=self.password_var)
        self.entry_password.grid(column=1, row=1, padx=5, pady=5, sticky="NSWE")

        self.message = tk.Label(self.frame, text="", fg="#0c1069", font=("Helvetica", 12, "bold"), height=10)
        self.message.grid(column=0, row=2, columnspan=2, sticky="NWE")

        self.btn_login = tk.Button(self.frame, text="Login", command=lambda: self.btn_clicked.set(1))
        self.btn_login.grid(column=0, row=3, columnspan=2)

    def create_loading_widgets(self):
        self.frame = ttk.Frame(self, padding="10 10 10 10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self.loading_bar = ttk.Progressbar(self.frame, mode="indeterminate", orient="horizontal")
        self.loading_bar.grid(column=0, row=0, padx=5, pady=5, sticky="SWE")
        self.loading_bar.start(100)

        self.message = tk.Label(self.frame, text="Loading...", fg="#0c1069", font=("Helvetica", 12, "bold"))
        self.message.grid(column=0, row=1, sticky="NWE")
        
    def on_login(self):
        if self.username_var.get() and self.password_var.get():
            self.message.config(text="Processing", fg="#0c1069")
            if self.webscraper_thread.done() and self.webscraper_thread.exception() is None:
                if self.logged_in:
                    self.after_login()
                    return
                self.webscraper_thread = self.executor.submit(verify_credentials, self.web["driver"], self.message, self.username_var.get(), self.password_var.get())
                self.webscraper_thread.add_done_callback(self.verification_callback)
                return
            print("Startup of scraper not done or called an exception")
            return
        self.message.config(text="Please fill in both fields.", foreground="#e62e09")
        if not self.message.winfo_exists():
            self.message.pack()

    def await_login(self):
        self.btn_login.wait_variable(self.btn_clicked)
        if self.verifying:
            self.await_login()
            return
        self.on_login()
        if self.logged_in:
            print("Successful Sign-in: Scrapping has started")
            self.after_login()
            return
        self.await_login()
    
    def after_login(self):
        self.webscraper_thread = self.executor.submit(monitor_traffic, self.web["driver"], self.web["proxy"])
        self.webscraper_thread.add_done_callback(self.scraping_callback)
        self.frame.destroy()
        self.create_loading_widgets()

    def startup_callback(self, future):
        print("Startup callback triggered")
        self.web = future.result()
        self.logged_in = bool(self.web["status"])

    def verification_callback(self, future):
        result = future.result()
        if result:
            self.after_login()
        else:
            self.message.config(text="Verification failed", fg="#e62e09")

    def scraping_callback(self, future):
        if future.done():
            try:
                self.end()
            except Exception as exc:
                print("Scraping had an exception")
                print(exc)
                print(future.exception())
                self.callback()
                self.mainwindow_callback()

    def force_end(self):
        try:
            self.destroy()
            self.update()
            self.callback()
            self.mainwindow_callback()
            self.web["server"].stop()
            self.web["driver"].quit()
            self.executor.shutdown(wait=False)
        except:
            self.executor.shutdown(wait=False)
            print("Force ended")

    def end(self):
        responses = exporter.get_responses()
        exporter.get_files(responses)
        self.web["server"].stop()
        self.web["driver"].quit()
        print("Server and driver quitted")
        print(self.webscraper_thread.done())
        self.executor.shutdown(wait=False)
        # When set to true, thread will not be able to join to main thread due to tkiners mainloop running.
        # potential solution: with statement for proper cleanup
        # for now, the threadpool will permanently be running in the background even after application closes lol
        print("Executor ended")
        self.destroy()
        self.update()
        self.callback()
        self.mainwindow_callback()
        print("Login Window destroyed")