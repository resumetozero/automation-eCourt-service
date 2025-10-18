import streamlit as st
from datetime import date
import time
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from scrapper_pipeline import scrapper_webpage, handle_alert, table_to_csv
from captcha_solver_ocr import captcha_solver
import os, sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="eCourts Downloader", layout="centered")
st.title("📄 eCourts Cause List Downloader")

if "driver" not in st.session_state:
    st.session_state.driver = scrapper_webpage(
        "https://services.ecourts.gov.in/ecourtindia_v6/?p=cause_list/"
    )
driver = st.session_state.driver


def wait_for_dropdown_refresh(driver, element_id, min_options=2, timeout=10):
    """Wait until dropdown has refreshed and contains > min_options."""
    WebDriverWait(driver, timeout).until(
        lambda d: len(Select(d.find_element(By.ID, element_id)).options) >= min_options
    )


def safe_select_dropdown(driver, element_id, retries=3, wait_refresh=False):
    """Fetch dropdown options safely (handles stale elements & AJAX refresh)."""
    for _ in range(retries):
        try:
            if wait_refresh:
                wait_for_dropdown_refresh(driver, element_id)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, element_id))
            )
            select_el = Select(driver.find_element(By.ID, element_id))
            options_dict = {
                o.get_attribute("value").strip(): o.text
                for o in select_el.options
                if o.get_attribute("value").strip() not in ["", "0"] and o.is_enabled()
            }
            if options_dict:
                return select_el, options_dict
        except StaleElementReferenceException:
            time.sleep(1)
        except Exception as e:
            st.error(f"Failed to fetch dropdown '{element_id}': {e}")
    return None, {}


def select_value_from_name(select_element, options_dict, selection_name):
    """Map user-visible name to value and select it."""
    val = next((k for k, v in options_dict.items() if v == selection_name), None)
    if val and select_element:
        try:
            select_element.select_by_value(val)
        except Exception as e:
            st.error(f"Failed to select dropdown '{selection_name}': {e}")
    return val

# --- State ---
with st.spinner("Fetching states..."):
    state_select_el, states_dict = safe_select_dropdown(driver, "sess_state_code")

# User must explicitly select a state (no auto preselection)
state_selected = st.selectbox(
    "Select State:", 
    ["-- Select State --"] + list(states_dict.values()), 
    key="state"
)

state_val = None
if state_selected != "-- Select State --":
    state_val = select_value_from_name(state_select_el, states_dict, state_selected)

# --- District (load only after user selects state) ---
district_disabled, districts_dict = True, {}
district_el = None

if state_val:
    with st.spinner("Fetching districts..."):
        districts_el, districts_dict = safe_select_dropdown(driver, "sess_dist_code", wait_refresh=True)
        district_disabled = not bool(districts_dict)

district_selected = st.selectbox(
    "Select District:",
    ["-- Select District --"] + (list(districts_dict.values()) if districts_dict else []),
    disabled=district_disabled,
    key="district"
)

district_val = None
if district_selected != "-- Select District --" and not district_disabled:
    district_val = select_value_from_name(districts_el, districts_dict, district_selected)



# --- Court Complex ---
court_complex_disabled, complexes_dict = True, {}
complexes_el = None

if district_val:
    with st.spinner("Fetching court complexes..."):
        complexes_el, complexes_dict = safe_select_dropdown(
            driver, "court_complex_code", wait_refresh=True
        )
        court_complex_disabled = not bool(complexes_dict)

court_complex_selected = st.selectbox(
    "Select Court Complex:",
    ["-- Select Court Complex --"] + (list(complexes_dict.values()) if complexes_dict else []),
    disabled=court_complex_disabled,
    key="court_complex"
)

court_complex_val = None
if court_complex_selected != "-- Select Court Complex --" and not court_complex_disabled:
    court_complex_val = select_value_from_name(complexes_el, complexes_dict, court_complex_selected)

handle_alert(driver)

# --- Court Establishment ---
court_disabled, courts_dict = True, {}
courts_el = None

if court_complex_val:
    with st.spinner("Fetching courts..."):
        courts_el, courts_dict = safe_select_dropdown(driver, "CL_court_no")
        court_disabled = not bool(courts_dict)

court_selected = st.selectbox(
    "Select Court Establishment (optional):",
    ["-- Select Court Establishment --"] + (list(courts_dict.values()) if courts_dict else []),
    disabled=court_disabled,
    key="court_establishment"
)

court_val = None
if court_selected != "-- Select Court Establishment --" and not court_disabled:
    court_val = select_value_from_name(courts_el, courts_dict, court_selected)

# Other Inputs
cause_date = st.date_input("Select Cause List Date (within 1 month):", value=date.today())
case_type = st.radio("Select Case Type:", ["Civil", "Criminal"])
case_type_val = "1" if case_type == "Civil" else "2"

# Fetch Button Action
if st.button("Fetch Cause List"):
    with st.spinner("solving captcha, please wait... ⏳"):

        try:
            date_input = driver.find_element(By.ID, "causelist_date")
            date_input.clear()
            date_input.send_keys(cause_date.strftime("%d-%m-%Y"))
        except Exception as e:
            st.error(f"Failed to fill date: {e}")

        # Wait for page load
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # CAPTCHA Solver
        result = captcha_solver(
            driver,
            img_id="captcha_image",
            input_id="cause_list_captcha_code",
            attempts=5,
            case_type=case_type_val,
            use_gpu=False
        )

    if result == "NoData":
        st.warning("⚠️ No records found for this selection.")
    elif result:
        # CAPTCHA successful and table expected
        with st.spinner("📊 Fetching cause list table..."):
            time.sleep(5)
            csv_file = "cause_list.csv"
            table_success = table_to_csv(driver, "dispTable", output_file=csv_file)

        if table_success:
            with open(csv_file, "rb") as f:
                st.download_button(
                    "📥 Download Cause List CSV",
                    f,
                    file_name=csv_file,
                    mime="text/csv"
                )
            st.success("✅ Cause list successfully fetched and ready for download!")
        else:
            st.warning("⚠️ Table not found or empty. Please recheck your filters or date.")
    else:
        st.error("❌ CAPTCHA solving failed or the page did not load correctly. Please try again.")
