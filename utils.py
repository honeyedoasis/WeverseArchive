import datetime
import mimetypes
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import filedate
import requests


def edit_creation_date(file_path, new_date: datetime):
    # print('Set ', full_path, ' to ', file_date)
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

def download_file(file_url, file_path, date=None, skip_exists=True, timeout=30):
    file_path = Path(file_path)
    if skip_exists and file_path.exists():
        return False

    existing_files = list(file_path.parent.glob(f"{file_path.name}.*"))
    if existing_files:
        # print(f"File already exists: {existing_files[0]}")
        return False

    file_path.parent.mkdir(parents=True, exist_ok=True)

    retries = 3
    for _ in range(retries):
        try:
            # Send a GET request to the URL
            response = requests.get(file_url, timeout=timeout)

            content_type = response.headers.get('content-type')

            extension = mimetypes.guess_extension(content_type.split(';')[0])

            if not extension:
                extension = ".bin"

            file_path = f'{file_path}{extension}'

            print(f"Download: {file_path} Date: {date} URL: {file_url}")

                # Check if the request was successful
            if response.status_code == 200:
                # Open a file in binary write mode to save the image
                with open(file_path, "wb") as file:
                    file.write(response.content)

                    if date:
                        edit_creation_date(file_path, date)
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


# if __name__ == '__main__':
    # url = 'https://phinf.wevpstatic.net/MjAyNDA4MDFfODQg/MDAxNzIyNTE0NDQ3MDQ3.jd8yLmvexdRXlwRBhZBoW5v3XgKgA3ilOhglifEW-0Eg.gdKTGmOlcsShILD35eY6Hbth7Ji9NeCwexY0unn5maog.JPEG/87dfb166-b56a-4167-aecc-d657305e5413.jpeg'
    # download_file(url, 'test.jpeg')
    # pass