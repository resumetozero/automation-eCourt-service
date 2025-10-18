import os
import time
import collections
import re
import cv2
import numpy as np
import pytesseract
import easyocr
import requests
from urllib.parse import urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException

os.makedirs("captcha_images", exist_ok=True)

def captcha_solver(driver, img_id, input_id, attempts=5, case_type="2", min_length=4, max_length=6, use_gpu=False):
    """
    Enhanced CAPTCHA solver using OpenCV preprocessing + Tesseract + EasyOCR.
    Auto-retries with candidate voting.
    """

    # Initialize EasyOCR
    reader = easyocr.Reader(['en'], gpu=use_gpu)

    # Tesseract OCR configs
    tesseract_psm = ["6","7","8","10"]  # Multiple PSM modes for reliability
    whitelist = "abcdefghijklmnopqrstuvwxyz0123456789"

    def transfer_cookies(sess):
        for c in driver.get_cookies():
            sess.cookies.set(c['name'], c['value'], domain=c.get('domain'), path=c.get('path'))
        return sess

    def preprocess_image(img_path):
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError("Failed to read image")

        # CLAHE for contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        img = clahe.apply(img)

        # Sharpen
        kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
        img = cv2.filter2D(img, -1, kernel)

        # Resize for better OCR
        img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        # Thresholding
        _, img_bin = cv2.threshold(img,0,255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img_bin_inv = cv2.bitwise_not(img_bin)
        return img_bin, img_bin_inv

    def run_ocr(img_bin, img_bin_inv):
        candidates = []

        # Tesseract
        for psm in tesseract_psm:
            config = f"--psm {psm} --oem 3 -c tessedit_char_whitelist={whitelist}"
            for img_variant in [img_bin, img_bin_inv]:
                text = pytesseract.image_to_string(img_variant, config=config).strip().lower()
                if text:
                    candidates.append(text)

        # EasyOCR
        for img_variant in [img_bin, img_bin_inv]:
            easy_text = ''.join(reader.readtext(img_variant, detail=0, allowlist=whitelist)).strip().lower()
            if easy_text:
                candidates.append(easy_text)

        return candidates

    def vote_candidate(candidates):
        """Return most likely candidate based on frequency and regex filtering"""
        pattern = f"[{whitelist}]{{{min_length},{max_length}}}"
        valid_candidates = [re.sub(r'[^a-z0-9]', '', c) for c in candidates]
        valid_candidates = [c for c in valid_candidates if re.fullmatch(pattern, c)]
        if not valid_candidates:
            return ""
        counter = collections.Counter(valid_candidates)
        return counter.most_common(1)[0][0]

    for attempt in range(1, attempts+1):
        try:
            img_el = driver.find_element(By.ID, img_id)
            src = img_el.get_attribute("src")
            if not src:
                raise RuntimeError("Captcha src not found")

            img_url = urljoin(driver.current_url, src)
            sess = transfer_cookies(requests.Session())
            headers = {"User-Agent": driver.execute_script("return navigator.userAgent;"),
                       "Referer": driver.current_url}
            sess.headers.update(headers)
            resp = sess.get(img_url, timeout=10, stream=True)
            if resp.status_code != 200:
                raise RuntimeError("Failed to download captcha image")

            img_path = f"./captcha_images/captcha_raw_{attempt}.png"
            with open(img_path, "wb") as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)

            img_bin, img_bin_inv = preprocess_image(img_path)
            candidates = run_ocr(img_bin, img_bin_inv)
            captcha_text = vote_candidate(candidates)

            if not captcha_text:
                print(f"[attempt {attempt}] OCR failed, refreshing captcha...")
                try:
                    refresh_btn = driver.find_element(By.XPATH, "//a[@title='Refresh Image' or contains(@onclick,'refreshCaptcha')]")
                    driver.execute_script("arguments[0].click();", refresh_btn)
                except:
                    time.sleep(1)
                continue

            # 3️⃣ Fill CAPTCHA
            input_el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, input_id)))
            input_el.clear()
            input_el.send_keys(captcha_text)
            print(f"[attempt {attempt}] CAPTCHA filled with: {captcha_text}")

            # 4️⃣ Click button
            btn_xpath = '//*[@id="frm_causelist"]/div[3]/div[2]/button[1]' if case_type=="1" else '//*[@id="frm_causelist"]/div[3]/div[2]/button[2]'
            btn_to_click = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, btn_xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_to_click)
            time.sleep(0.5)
            try: btn_to_click.click()
            except: driver.execute_script("arguments[0].click();", btn_to_click)

            # 5️⃣ Check CAPTCHA error modal
            try:
                close_btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-close[data-bs-dismiss='modal']"))
                )
                close_btn.click()
                print("❌ Wrong CAPTCHA modal closed. Retrying...")
                continue
            except TimeoutException:
                pass  # No modal → proceed

            # 6️⃣ Check result
            try:
                WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.ID, "dispTable")))
                print("✅ Table found, ready to scrape!")
                return True
            except TimeoutException:
                try:
                    driver.find_element(By.ID, "nodata")
                    print("ℹ️ No records found for this query.")
                    return "NoData"
                except NoSuchElementException:
                    print("❌ Unexpected page state, retrying...")

        except Exception as e:
            print(f"[attempt {attempt}] error: {e}")
            time.sleep(1)

    print("⚠️ All CAPTCHA attempts failed.")
    return False
