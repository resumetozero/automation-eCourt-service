from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException, TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# from captcha_solver_ocr import captcha_solver
# from captcha_solver_hf import captcha_solver
# from captcha_ocr_basic import captcha_solver

import time
import csv

# import os , sys
# sys.path.append(os.path.dirname(os.path.abspath(__file__))) 


def scrapper_webpage(url):
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-close[data-bs-dismiss='modal']"))
        )
        close_btn.click()
        print("✅ Initial modal closed.")
    except TimeoutException:
        print("ℹ️ No initial modal found.")
        
    return driver



def handle_alert(driver):
    # Accepts any open alert pop-up if present
    try:
        WebDriverWait(driver, 2).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        print(f"⚠️ Alert Text: {alert.text}")
        alert.accept()
        print("✅ Alert accepted.")
    except NoAlertPresentException:
        pass
    except Exception as e:
        print(f"Error handling alert: {e}")



# def get_drop_down_data(driver,name):
#     data={}
#     WebElement_options=WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, name)))
#     if not WebElement_options:
#         print(f"❌ Dropdown with ID '{name}' not found.")
#         return False
    
#     if not WebElement_options.is_displayed():
#         print(f"ℹ️ Dropdown '{name}' is not visible. Skipping.")
#         return False
    
#     data_dropdown = Select(WebElement_options)
    
#     for opt in data_dropdown.options:
#         v=opt.get_attribute("value").strip()
#         is_disabled = opt.get_attribute("disabled")
#         if v!= "0" and v!='' and not is_disabled:
#             data[v]=opt.text
    
#     if not data:
#         print(f"❌ No options found in dropdown '{name}'.")
#         return False
    
#     print(f"\nAvailable {name}:")
#     for v, s in data.items():
#         print(f"{v} --> {s}")

#     user_input_states = input(f"Enter the {name} name or value: ").strip()

#     selected_value = None
#     if user_input_states in data:
#         selected_value = user_input_states
#     else:
#         for val, text in data.items():
#             if text.lower() == user_input_states.lower():
#                 selected_value = val
#                 break

#     if not selected_value:
#         print("❌ Invalid selection.")
#         return False

#     # Select the chosen state
#     data_dropdown.select_by_value(selected_value)
#     print(f"✅ Selected {name}: {data_dropdown.first_selected_option.text}")
#     return True



def table_to_csv(driver, table_id, output_file="output.csv"):
    try:
        table_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, table_id))
        )
        table_html = table_element.get_attribute("outerHTML")
        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find("table", {"id": table_id})
        if not table:
            print(f"❌ No table found with id={table_id}.")
            return False

        # Extract headers
        headers = [th.get_text(strip=True) for th in table.find_all("th")]

        # Extract rows
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            row = [cell.get_text(" ", strip=True) for cell in cells]
            if row and not all(x == "" for x in row):
                rows.append(row)

        # Remove section headers like "Misc. Arguments" (single-column rows)
        rows = [row for row in rows if not (len(row) == 1 and "color:#3880d4" in str(row))]

        # Write to CSV
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows[1:])

        print(f"✅ Table successfully saved to: {output_file}")
        return True

    except (NoSuchElementException, TimeoutException) as e:
        print(f"❌ Error locating table with id={table_id}: {e}")
        return False

# if __name__ == "__main__":

#     url = "https://services.ecourts.gov.in/ecourtindia_v6/?p=cause_list/"
#     driver = scrapper_webpage(url)

    # try:
    #     #getting states
    #     if get_drop_down_data(driver,"sess_state_code"):
    #         time.sleep(3)

    #         #getting districts
    #         if get_drop_down_data(driver,"sess_dist_code"):
    #             time.sleep(3)

    #             #getting court complex
    #             if get_drop_down_data(driver,"court_complex_code"):
    #                 handle_alert(driver)
    #                 time.sleep(3)

    #                 #getting court establishment is some cases
    #                 get_drop_down_data(driver,"court_est_code")

    #                 #getting court name
    #                 get_drop_down_data(driver,"CL_court_no")

                    # #date selection
                    # date_input = driver.find_element(By.ID, "causelist_date")
                    # date_input.clear()
                    # date_input.send_keys(input("Date format (DD-MM-YYYY) within 1 month: ").strip())
                    # case_type = ""
                    # while case_type not in ["1", "2"]:
                    #     print("""Select case type:
                    #     \n1 --> Civil
                    #     \n2 --> Criminal""")
                    #     case_type = input("Enter 1 or 2: ").strip()
                    # #captcha solving
                    # if captcha_solver(driver, img_id="captcha_image", input_id="cause_list_captcha_code", attempts=5,case_type = case_type, use_gpu=False):
                    #     time.sleep(5)
                    #     #extracting table data
    #                 #     table_to_csv(driver,"dispTable","cause_list.csv")
                    
    # except Exception as e:
    #     print(f"Error: {e}")
    # finally:
    #     print("Scraping completed.")
    #     driver.quit()