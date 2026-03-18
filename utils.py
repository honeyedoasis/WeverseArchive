import base64
import datetime
import mimetypes
import time
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import filedate
import requests


def edit_creation_date(file_path, new_date: datetime):
    if new_date is None:
        return
        # print('Edit creation date ', new_date)

    file = filedate.File(file_path)
    file.created = new_date
    file.modified = new_date
    file.accessed = new_date


# def download_img(image_url, file_path, date=None, skip_exists=True, timeout = 5):
#     file_path = Path(file_path)
#     if skip_exists and file_path.exists():
#         return True
#
#     file_path.parent.mkdir(exist_ok=True)
#
#     for i in range(3): # try 3 times
#         try:
#             # Send a GET request to the URL
#             print(f"Download: {file_path} URL: {image_url} Date: {date}")
#             response = requests.get(image_url, timeout=timeout)
#
#             if response.status_code == 200:
#                 with open(file_path, "wb") as file:
#                     file.write(response.content)
#                     print("Image downloaded successfully!")
#
#                     if date:
#                         edit_creation_date(file_path, date)
#                 return True
#             else:
#                 print(f"Failed to download image. Status code: {response.status_code}")
#         except Exception as e:
#             print(f"An error occurred: {e}")
#
#     return False

def has_file_matching_name(file_path):
    file_path = Path(file_path)
    existing_files = list(file_path.parent.glob(f"{file_path.name}.*"))
    return len(existing_files) != 0

def download_file(file_url, file_path, date=None, skip_exists=True, timeout=30):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if skip_exists and has_file_matching_name(file_path):
        return False
    # existing_files = list(file_path.parent.glob(f"{file_path.name}.*"))
    # if existing_files:
    #     # print(f"File already exists: {existing_files[0]}")
    #     return False

    retries = 3
    for _ in range(retries):
        try:
            # Send a GET request to the URL
            response = requests.get(file_url, timeout=timeout)

            content_type = response.headers.get('content-type')

            extension = mimetypes.guess_extension(content_type.split(';')[0])

            if not extension:
                extension = ".bin"

            final_path = f'{file_path}{extension}'
            if skip_exists and Path(final_path).exists():
                return False

            print(f"Download: {final_path} Date: {date} URL: {file_url}")

                # Check if the request was successful
            if response.status_code == 200:
                # Open a file in binary write mode to save the image
                with open(final_path, "wb") as file:
                    file.write(response.content)

                    if date:
                        edit_creation_date(final_path, date)
                    # print("Downloaded successfully!")
                return True  # Exit the loop if download is successful
            else:
                print(f"Failed to download image. Status code: {response.status_code}. Retrying...")
                time.sleep(3)
        except Exception as e:
            print(f"An error occurred: {e}. Retrying...")
            time.sleep(3)

    return False

def isotime(date_str):
    """
    2026-03-17T16:25:52+0900
    """
    return datetime.datetime.fromisoformat(date_str)

def timestamp(ts):
    """
    1773733615640
    """
    ts_seconds = ts / 1000
    return datetime.datetime.fromtimestamp(ts_seconds, tz=ZoneInfo("Asia/Seoul"))


def get_pssh_from_mpd(mpd_text):
    """
    Extracts the Widevine PSSH from MPD text, ignoring namespace variations.
    """
    # Parse the XML
    root = ET.fromstring(mpd_text)

    # Widevine System ID
    WIDEVINE_UUID = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"

    # 1. Iterate through all elements in the MPD
    for elem in root.iter():
        # Look for ContentProtection tags (ignoring the namespace prefix)
        if elem.tag.endswith('ContentProtection'):
            scheme_id = elem.attrib.get('schemeIdUri', '').lower()

            # 2. Check if this is the Widevine block
            if WIDEVINE_UUID in scheme_id:
                # 3. Search children of this tag for 'pssh'
                for child in elem:
                    if child.tag.endswith('pssh'):
                        pssh_b64 = child.text.strip()
                        return pssh_b64

    return None

def get_url_filename(url, no_ext=True):
    parsed_url = urlparse(url)
    return PurePosixPath(parsed_url.path).stem if no_ext else parsed_url.path


def get_url_date(url):
    """
    Expecting a url in the format
    https://phinf.wevpstatic.net/MjAyMjA3MTZfODQg/MDAxNjU3OTAxNTA3OTYw.XicWQ6eh1gk6nIC4GFtqWKCDiFZQCMLPvQ2lUqOjjxwg.6tnIZEYqlfnbR03YaBitEi1SxQldnjVGcnlTpMK37oAg.JPEG/aab3aeaf86d149b2aa73f9a793eebfea888.jpg
    """
    if not url.startswith('https://phinf.wevpstatic.net/'):
        print('Failed to parse url date for', url)
        breakpoint()

    path_parts = urlparse(url).path.strip('/').split('/')
    date_part_encoded = path_parts[0]  # "MjAyMzExMjNfNDgg"

    # Decode it and take the first 8 characters (YYYYMMDD)
    date_str = base64.b64decode(date_part_encoded).decode('utf-8')[:8]

    return date_str


# if __name__ == '__main__':
    # url = 'https://phinf.wevpstatic.net/MjAyNDA4MDFfODQg/MDAxNzIyNTE0NDQ3MDQ3.jd8yLmvexdRXlwRBhZBoW5v3XgKgA3ilOhglifEW-0Eg.gdKTGmOlcsShILD35eY6Hbth7Ji9NeCwexY0unn5maog.JPEG/87dfb166-b56a-4167-aecc-d657305e5413.jpeg'
    # download_file(url, 'test.jpeg')
    # pass