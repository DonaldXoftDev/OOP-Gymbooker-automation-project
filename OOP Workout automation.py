from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver import ChromeOptions
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
APP_PASSWORD = os.getenv('APP_PASSWORD')
WEB_URL = 'https://appbrewery.github.io/gym'

chrome_options = ChromeOptions()
chrome_options.add_experimental_option("detach", True)

#create selenium user_profile
user_data_dir = os.path.join(os.getcwd(), 'chrome_profile')

#store profile info in specified directory
chrome_options.add_argument(f'--user-data-dir={user_data_dir}')

#open website
driver = webdriver.Chrome(options=chrome_options)


class GymBooker:
    def __init__(self, url, web_driver, email, password, items_to_book: list):
        self.url = url
        self.driver = web_driver
        self.email = email
        self.password = password
        self.wait = WebDriverWait(self.driver, 10)
        self.day_time_list = items_to_book

        if not self.email or self.password:
            raise ValueError('Email and password are required. Please Enter the details in the .env file.')

        self.driver.get(url)
        self.driver.maximize_window()

        self.retry(self.login, description='login')

        # book a gym class
        class_filter = self.wait.until(ec.presence_of_element_located((By.ID, 'type-filter'))
                                       )
        class_filter.click()

        # filter the schedule page for an exercise class
        filter_by = self.wait.until(
            ec.presence_of_element_located((By.XPATH, '//*[@id="type-filter"]/option[3]'))
        )
        filter_by.click()

        self.data_dict = self.start_booking_process()
        self.unique_data_list = self.data_dict['unique_data_list']
        self.generic_data_list = self.data_dict['generic_data_list']

        # navigate to the bookings page
        my_bookings_page = self.wait.until(
            ec.presence_of_element_located((By.ID, 'my-bookings-link'))
        )
        my_bookings_page.click()

        self.booking_cards = self.driver.find_elements(By.CSS_SELECTOR, value='[id^="booking-card"]')

        self.waitlist_cards = self.driver.find_elements(By.CSS_SELECTOR, value='[id^="waitlist-card"]')

        self.all_bookings_count = len(self.booking_cards) + len(self.waitlist_cards)

        print('\n---Total classes on bookings page:', self.all_bookings_count)

        self.preview_verification_results()
        self.show_booking_summary()

    #main controller that does the whole booking
    def start_booking_process(self):

        data_list = []
        unique_data_list = []
        seen_identifiers = set()
        for item in self.day_time_list:
            class_to_book, filtered_section, btn_state = self.retry(self.book_gym_class, item[0], item[1],
                                                                    description='booking')
            results = self.generate_booking_data(class_to_book, filtered_section, btn_state)

            print(results['message'])

            if results['status'] in ['error', 'not_found']:
                print(f'the status is "{results["status"]}"')
            else:
                data_list.append(results)

                identifier = results['booking_data']
                if identifier not in seen_identifiers:
                    unique_data_list.append(results)
                    seen_identifiers.add(identifier)

        return {
            'generic_data_list': data_list,
            'unique_data_list': unique_data_list
        }

    # Helper functions -------------------------------
    def get_data_dict(self, message: str, data: str, status: str) -> dict:
        return {
            'status': status,
            'booking_data': data,
            'message': f'{message}: {data}',
        }

    def booked_details(self, data: str) -> dict:
        return self.get_data_dict(message='Already booked', data=data, status='already booked')

    def waitlist_details(self, data: str) -> dict:
        return self.get_data_dict(message='Already waitlisted', data=data, status='already waitlisted')

    def do_booking_details(self, data: str) -> dict:
        return self.get_data_dict(message='✅Successfully booked', data=data, status='booked')

    def join_waitlist_details(self, data: str) -> dict:
        return self.get_data_dict(message='✅Joined Waitlist on', data=data, status='waitlisted')

    def determine_verification_message(self, expected_count: int, found_count: int):
        if expected_count == found_count:
            return f'\t✅ SUCCESS: All bookings verified'
        return f'\t❌ MISMATCH: Missing {expected_count - found_count} bookings'

    def preview_verification_results(self):
        verifications = self.retry(self.verify_bookings, description='bookings page')

        print('\n---Verifying On My Bookings Page---')
        for item in verifications:
            print('\t✔Verified: ', item)

        verification_status = self.determine_verification_message(len(self.unique_data_list), self.all_bookings_count)

        print('\n---Verification results---')
        print(f'\tExpected: {len(self.unique_data_list)} bookings')
        print(f'\tFound: {self.all_bookings_count} bookings')
        print(verification_status)

    def show_booking_summary(self):
        bookings, details = self.booking_summary(self.generic_data_list)

        print('\n------BOOKING SUMMARY--------')
        for key, value in bookings.items():
            print(f'{key.title()}: {value}')

        print('\n------DETAILED CLASS LIST------')
        for detail in details:
            if detail is not None:
                print(f'⚫ {detail}')

    def retry(self, function, *args, retries=7, description=None):
        print('\n')
        for i in range(retries):

            print(f'Trying {description}. Attempt {i + 1}.')
            try:
                return function(*args)
            except TimeoutException:
                if i == retries - 1:
                    raise TimeoutException(f"Error: done retrying {description}")
                time.sleep(0.09)

    # main methods---------------------------------
    def login(self):
        """Logs the user in using their credentials ->
            email, password"""
        login_btn = self.wait.until(
            presence_of_element_located((By.ID, 'login-button'))
        )
        login_btn.click()

        my_email = self.wait.until(
            ec.presence_of_element_located((By.ID, 'email-input'))
        )
        my_email.clear()
        my_email.send_keys(self.email)

        my_pass_word = self.driver.find_element(By.ID, 'password-input')
        my_pass_word.clear()
        my_pass_word.send_keys(self.password)

        submit_btn = self.driver.find_element(By.ID, 'submit-button')
        submit_btn.click()

        # wait for schedule page to load
        self.wait.until(ec.presence_of_element_located((By.ID, 'schedule-page')))

    def filter_section_by_day(self, day_to_filter: str):
        """isolate the section of the day to book
        egs: Thu section can have 2 exercise classes with different times
        """

        class_days = self.driver.find_elements(By.CSS_SELECTOR, value='[id^="day-group"]')

        filtered_section = {}
        for section in class_days:
            try:
                day_title_element = section.find_element(By.CSS_SELECTOR, value='[id^="day-title"]')
                day_title_text = day_title_element.text.strip()

                if day_to_filter in day_title_text:
                    filtered_section['day_title'] = day_title_text
                    filtered_section['section'] = section
                    break
            except Exception as e:
                print(e)
                continue

        return filtered_section

    def get_class_to_book(self, target_time: str, available_slots: list[WebElement]):
        """returns a dictionary of class details for the target time
        uses try except blocks to skip over elements that are malformed """

        class_to_book = {}
        for slot in available_slots:
            try:
                class_time = slot.find_element(By.CSS_SELECTOR, value='[id^="class-time"]').text

                # self.wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, '[id^="book-button"]')))

                if target_time in class_time:
                    class_name = slot.find_element(By.CSS_SELECTOR, value='[id^="class-name"]').text
                    book_btn = slot.find_element(By.CSS_SELECTOR, value='[id^="book-button"]')
                    class_to_book['class_name'] = class_name
                    class_to_book['class_time'] = ' '.join(class_time.split()[1:])
                    class_to_book['book_btn'] = book_btn

            except NoSuchElementException:
                print(f'Warning: Skipped a malformed element slot in the list.')

        return class_to_book

    def book_gym_class(self, t_day, t_time):
        if not t_day or not t_time:
            return {'status': 'error', 'message': 'no time  or day specified'}

        filtered_section = self.filter_section_by_day(t_day)

        if not filtered_section:
            return {'status': 'not_found', 'message': f'No section for {t_day}'}

        slots = filtered_section['section'].find_elements(By.CSS_SELECTOR, value='[id^="class-card"]')

        class_to_book = self.get_class_to_book(t_time, slots)

        if not class_to_book:
            return {'status': 'not_found', 'message': f'No available classes found for {t_time} on {t_day}.'}

        book_btn = class_to_book['book_btn']
        initial_btn_text = book_btn.text.lower()

        if initial_btn_text in ['booked', 'waitlisted']:
            return class_to_book, filtered_section, initial_btn_text

        book_btn.click()

        try:
            self.wait.until(
                lambda web_driver: book_btn.text.lower() in ['booked', 'waitlisted'],
            )

        except TimeoutException:
            raise TimeoutException('\nWarning: Button state did not change after click!')

        return class_to_book, filtered_section, initial_btn_text

    def generate_booking_data(self, class_to_book: dict, filtered_section: dict, initial_btn_state) -> dict:
        booking_data = f'{class_to_book['class_name']} for {class_to_book['class_time']} by {filtered_section['day_title']}'

        time.sleep(0.05)

        if initial_btn_state in ['booked', 'waitlisted']:
            data = self.booked_details if initial_btn_state == 'booked' else self.waitlist_details

        elif initial_btn_state == 'join waitlist':
            data = self.join_waitlist_details

        elif initial_btn_state == 'book class':
            data = self.do_booking_details

        else:
            return self.get_data_dict(message='invalid button state with text', data=initial_btn_state, status='error')

        return data(booking_data)

    def booking_summary(self, result: list[dict]):
        stats = {'booked': 0, 'waitlisted': 0, 'already booked': 0, 'already waitlisted': 0}

        new_entries = []
        for data in result:
            entries_dict = {
                'booked': f'[New Booking]: {data['booking_data']}',
                'waitlisted': f'[New Waitlist]: {data['booking_data']}',
                'already booked': f'[Booked]: {data['booking_data']}',
                'already waitlisted': f'[Waitlisted]: {data['booking_data']}',

            }

            status = data['status'].lower()
            if status in stats:
                stats[status] += 1
                entry = entries_dict.get(status, None)
                new_entries.append(entry)

        summary = {
            'new bookings': stats['booked'],
            'new waitlists': stats['waitlisted'],
            'already booked/waitlisted': stats["already booked"] + stats["already waitlisted"],
            'total processed classes': len(result)
        }
        return summary, new_entries

    def verify_bookings(self):
        expected_set = set()
        for data in self.unique_data_list:
            tried_to_book_name = ' '.join(data['booking_data'].split()[:2])
            expected_set.add(tried_to_book_name)

        found_set = set()
        for data in self.booking_cards:
            try:
                booked_name = data.find_element(By.CSS_SELECTOR, '[id^="booking-class-name"]').text
                found_set.add(booked_name)
            except NoSuchElementException:
                continue

        for data in self.waitlist_cards:
            try:
                waitlist_name = data.find_element(By.CSS_SELECTOR, '[id^="waitlist-class-name"]').text
                found_set.add(waitlist_name)
            except NoSuchElementException:
                continue

        verified_bookings = expected_set.intersection(found_set)

        return verified_bookings


day_time_list = [('Thu', '6:00'), ('Fri', '6:00'), ('Fri', '8:00'), ('Fri', '6:00')]

gym_booker = GymBooker(WEB_URL, driver, EMAIL_ADDRESS, APP_PASSWORD, day_time_list)
