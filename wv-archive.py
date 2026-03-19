import json
import os
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import requests
import yt_dlp
import time
import xmltodict
from pywidevine import PSSH, Device, Cdm
from yt_dlp import YoutubeDL

from yt_dlp.extractor.weverse import WeverseIE
from yt_dlp.utils import ExtractorError

import utils

COMMUNITY_NAME = 'fromis9'
COMMUNITY_ID = 36

ydl_params = {
    # 'verbose': True,
    'quiet': True,
    'cookiesfrombrowser': ('firefox',),
}

MEDIA_FOLDER = 'media'
JSON_FOLDER = 'json-data'

LIVE_POSTS_FOLDER = 'liveTabPosts'
ARTIST_POSTS_FOLDER = 'artistTabPosts'

WRITE_POST_COMMENTS = False
WRITE_LIVE_COMMENTS = False
WRITE_ARTIST_COMMENTS = False

DOWNLOAD_MOMENTS_JSON = True
DOWNLOAD_MOMENTS_MEDIA = True
DOWNLOAD_LIVE_VODS = True  # this one will take forever to process
DOWNLOAD_POST_MEDIA = False
DOWNLOAD_PROFILE_PICTURES = True
DOWNLOAD_OFFICIAL_MEDIA = False  # The media in this tab https://weverse.io/fromis9/media?tab=all

PAGED_SLEEP = 10
SHORT_SLEEP = 0.5

WVD_DEVICE_PATH = "F:/Programs/Tools/drm-tools/CDMs/1668035862.wvd"

def get_media_path():
    return f'{COMMUNITY_NAME}/{MEDIA_FOLDER}'

def get_json_path():
    return f'{COMMUNITY_NAME}/{JSON_FOLDER}'

def get_media_json_path():
    return f'{get_json_path()}/searchAllMedia.json'


def get_live_json_path():
    return f'{get_json_path()}/liveTabPosts.json'


def get_artist_json_path():
    return f'{get_json_path()}/artistTabPosts.json'


# # What was this for?
# rooms = {
#     'jiheon': '414361',  # jh
#     'hayoung': '297243',  # hy
#     'chaeyoung': '329164',  # cy
#     'jiwon': '464268',  # jw
#     'jisun': '221087',  # js
#     'saerom': '321529',  # sr
#     'seoyeon': '229217',  # sy
#     'nagyung': '233441',  # ng
# }

passwords = {
    '0-119852324': '',
    '0-59825': '1154',
    '0-58709': '0107',
    '4-120566436': '0124',
    '1-7529': '0601',
    '0-54144': '0122',
    '1-119817916': '0124',
    '3-120472027': '7777',
    '3-120082099': '1123',
    '4-119844206': '0605',
    '4-120717949': '0320',
    '1-119739859': '4444',
    '2-120747570': '0320',
    '0-119985805': '1111',
    '0-3962': '1004',
    '0-4013': '360',
    '0-104750': 'BABABABAB',
}

"""
Get this by finding the profile of the official channel
Example: https://weverse.io/fromis9/profile/58afde0dbc1fccd94cd44eff91fa3673
"""
official_channels = [
    # '47b84d66038c899cfc87e38df8b92143', # fromis_9
    # '58afde0dbc1fccd94cd44eff91fa3673'  # floverse_9
    # '4e3e72a5b2ea6ad2c3ac319a4dbc26d0', # Weverse
]

ext = None


def make_extractor():
    global ext
    if ext is None:
        ydl = yt_dlp.YoutubeDL(ydl_params)

        ext = WeverseIE()
        ext.set_downloader(ydl)
        ext.initialize()

    return ext


def get_next_page(json_data):
    paging = json_data['paging']
    if param := paging.get('nextParams'):
        return param['after']  # .replace(',', '%2C')

    return None


def get_prev_page(json_data):
    paging = json_data['paging']
    if param := paging.get('previousParams'):
        if prev := param.get('prev'):
            return prev  # .replace(',', '%2C')

        if prev := param.get('before'):
            return prev  # .replace(',', '%2C')

        # FAILED TO FIND PREV PAGE?
        breakpoint()

    return None


def run_extr(extr, req, out_data=None, grab_data=True, post=False):
    print(req)
    if post:
        grab_data = False

    while True:
        try:
            post_byte = b'' if post else None
            json_data = extr._call_api(req, '', data=post_byte)
            break
        except Exception as e:
            print(e)
            return None

    if out_data is not None:
        if grab_data:
            post_data = json_data['data']
            out_data += post_data
            print(f'Found data {len(post_data)} Data: {len(out_data)}')
        else:
            out_data.append(json_data)
            print(len(out_data))

    return json_data


def save_progress(filename, data):
    """Helper to save the current data list to a JSON file safely."""
    file_path = Path(filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_resume_state(filename):
    """Helper to load the last used cursor for pagination."""
    state_path = Path(f"{filename}.state")
    if state_path.exists():
        return json.loads(state_path.read_text(encoding='utf-8'))
    return None


def save_resume_state(filename, cursor, processed_indices=None):
    """Helper to save the current cursor/progress state."""
    state_path = Path(f"{filename}.state")
    state = {"cursor": cursor, "processed_indices": processed_indices or []}
    state_path.write_text(json.dumps(state), encoding='utf-8')


def write_paged_requests(req, initial_req, filename, use_after, skip_exists=False):
    """
    Processes paginated requests.
    Saves the 'after' or 'prev' cursor to a .state file to resume.
    """
    file_path = Path(filename)
    if skip_exists and file_path.exists():
        print(f"File {filename} exists, skipping.")
        return json.loads(file_path.read_text(encoding='utf-8'))

    out_data = []
    current_cursor = None

    # Resume logic
    if file_path.exists():
        try:
            state = get_resume_state(filename)
            if state:
                current_cursor = state.get("cursor")
                print(f"Resuming {filename} from cursor: {current_cursor}")
                # with open(file_path, 'r', encoding='utf-8') as f:
                out_data = json.loads(file_path.read_text(encoding='utf-8'))
            else:
                print(f"{file_path} state complete, returning")
                return json.loads(file_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"Could not resume: {e}")

    extr = make_extractor()
    initial = initial_req if not current_cursor else None

    while True:
        mod_req = req

        # If we have a stored cursor, apply it immediately
        if current_cursor:
            param_key = 'after' if use_after else 'prev'
            # Check if req already has query params
            separator = '&' if '?' in mod_req else '?'
            mod_req += f'{separator}{param_key}={current_cursor}'
        elif initial:
            mod_req = initial
            initial = None

        # Fetch data
        data = run_extr(extr, mod_req, out_data)

        # Get next cursors
        prev_cursor = get_prev_page(data)
        after_cursor = get_next_page(data)

        # Update current cursor based on mode
        current_cursor = after_cursor if use_after else prev_cursor

        # Save current results and cursor to disk
        save_progress(filename, out_data)
        save_resume_state(filename, current_cursor)

        # Termination logic
        if use_after and not after_cursor:
            break
        elif not use_after and not prev_cursor:
            break

        print(f"Waiting... Next cursor: {current_cursor}")
        time.sleep(PAGED_SLEEP)

    # Clean up state file if finished
    state_path = Path(f"{filename}.state")
    if state_path.exists():
        state_path.unlink()
    print(f"Finished {filename}")
    return out_data


def call_request(req, post=False):
    extr = make_extractor()
    resp = run_extr(extr, req, post=post)
    time.sleep(SHORT_SLEEP)
    return resp


def write_single(req, filename, skip_exists=True):
    file_path = Path(f'{filename}')
    if skip_exists and file_path.exists():
        return json.loads(file_path.read_text(encoding='utf-8'))

    extr = make_extractor()
    data = run_extr(extr, req)
    if data:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data, indent=4), encoding='utf-8')

    time.sleep(SHORT_SLEEP)

    return data


def write_individual_posts(post_file, folder, write_comments=False):
    posts = []

    with open(post_file, 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            posts.append(data['postId'])

    out_data = []
    for post_id in posts:
        req = f'/post/v1.0/post-{post_id}?fieldSet=postV1'
        if password := passwords.get(post_id):
            req += f"&lockPassword={password}"
            print(f'Downloading locked post {post_id} with pass {password}')

        data = write_single(req, f'{get_json_path()}/{folder}/{post_id}.json', True)

        out_data.append(data)

        if write_comments:
            print(f'Writing post comments {post_id}')
            req = f'/comment/v1.0/post-{post_id}/comments?fieldSet=postCommentsV1'
            write_paged_requests(req, req, f'{get_json_path()}/{folder}/{post_id}.comments.json', True)

    return out_data


def download_extension_video(data, filepath):
    # TODO maybe just use yt-dlp?
    video_id = data['extension']['video']['videoId']
    post_id = data['postId']
    date = utils.timestamp(data['publishedAt'])

    if data['membershipOnly']:
        return

    if utils.has_file_matching_name(filepath):
        return

    vod_data = get_vod_video_json(video_id)
    url = get_vod_url(vod_data)
    print('Downloading video ', post_id, filepath)
    utils.download_file(url, filepath, date)


def write_live_chat():
    posts = []

    with open(f'{get_json_path()}/all_live_posts.json', 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            postId = data['postId']
            media_info = data['extension']['mediaInfo']
            if chat := media_info.get('chat'):
                artist_msgs = chat['artistMessages']
                if len(artist_msgs['data']):
                    posts.append((chat['chatId'], data))
            else:
                print('No chat id?', postId, data['shareUrl'])
                break

    for chatId, data in posts:
        postId = data['postId']
        req = f'/chat/v1.0/chat-{chatId}/artistMessages'
        # print(req, postId, data['shareUrl'])
        write_paged_requests(req, req, f'{get_json_path()}/liveChat/{postId}.json', True, True)
        time.sleep(5)


def write_official_media(community_id):
    req = f'/media/v1.0/community-{community_id}/searchAllMedia?fieldSet=postsV1'
    return write_paged_requests(req, req, get_media_json_path(), True)


def get_vod_video_json(video_id):
    '''
    '/video/v2.1/vod/75098/playInfo?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&communityId=36&gcc=AU&language=en&os=WEB&platform=WEB&playerType=html5_pc&resType=xml&version=v3&wpf=pc&wmd=%2FPk5HfwkvBmU4hspD%2F2u%2BhROCIQ%3D&wmsgpad=1773734785779'
    '''
    req = f'/video/v2.1/vod/{video_id}/playInfo?version=v3'
    return call_request(req)


def get_vod_url(data):
    playback_xml = data['playback']

    data = xmltodict.parse(playback_xml)
    print(data)
    # videos = data['videoSource']['videos']['video']
    types = data['MPD']['Period']['AdaptationSet']
    adaption_set = next((v for v in types if v['@mimeType'] == 'video/mp4'), None)
    videos = adaption_set['Representation']

    def video_size(v):
        return int(v['@bandwidth'])

    return sorted(videos, key=video_size, reverse=True)[0]['BaseURL']


def get_cvideo_json(video_id):
    # '/cvideo/v1.0/cvideo-4-960370/'
    # 'https://global.apis.naver.com/weverse/wevweb/cvideo/v1.0/cvideo-4-960370/playInfo?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&language=en&os=WEB&platform=WEB&videoId=4-960370&wpf=pc&wmd=pPj2kgvK3Lqe3%2BCodfuB%2BDOs3cY%3D&wmsgpad=1773719263715'
    req = f'/cvideo/v1.0/cvideo-{video_id}/playInfo?videoId={video_id}'
    return call_request(req)


def download_cvideo_json(video_id, path, date=None):
    data = get_cvideo_json(video_id)
    print(data)
    videos = data['playInfo']['videos']['list']
    highest_quality = max(videos, key=lambda x: x["size"])
    print(highest_quality)
    url = highest_quality['source']
    utils.download_file(url, path, date=date)


def write_live_tab_posts(community_id):
    req = f'/post/v1.0/community-{community_id}/liveTabPosts'
    write_paged_requests(req, req, get_live_json_path(), True)

    # if True:
    # print('Bla')
    # with open(f'{json_location}', 'r', encoding='utf-8') as file:
    #     json_data = json.load(file)
    #     for data in json_data:
    #         postId = data['postId']
    #         media_info = data['extension']['mediaInfo']
    #         if chat := media_info.get('chat'):
    #             posts.append((chat['chatId'], data))
    #             # artist_msgs = chat['artistMessages']
    #             # if len(artist_msgs['data']):
    #             #     posts.append((chat['chatId'], data))
    #         else:
    #             print('No chat id?', postId, data['shareUrl'])
    #             break
    #
    # '/chat/v1.0/chat-N1XTf9/messages?after=1733566168468%2C4b0a80d517a7229bf3747c89dc04e457&limit=50'
    # '/chat/v1.0/chat-N1VwSq/messages?limit=50&appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&language=en&os=WEB&platform=WEB&wpf=pc&wmsgpad=1736165949156&wmd=gvpNwpjvWqh1sc1eiuqDk4eqeDA%3D'
    # '/chat/v1.0/chat-N1XTf9/messages?after=1733566168468%2C4b0a80d517a7229bf3747c89dc04e457&limit=50&appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&language=en&os=WEB&platform=WEB&wpf=pc&wmsgpad=1736165384857&wmd=4CuFyOOaJ7JnTQ0PbDxo5uPDUmI%3D'
    #
    # for chatId, data in posts:
    #     postId = data['postId']
    #     req = f'/chat/v1.0/chat-{chatId}/messages?limit=1000'
    #     print(req, postId, data['shareUrl'])
    #     write_all_requests(req, req, f'{output_folder}/{postId}', True, True)
    #     # break


def get_artists(community_id):
    req = f'/artistpedia/v1.0/community-{community_id}/highlight'
    if data := write_single(req, f'{get_json_path()}/artistProfiles.json', skip_exists=True):
        return data['artistProfiles']

    print('Error failed to get artists')
    return None


# 'https://global.apis.naver.com/weverse/wevweb/post/v1.0/member-67b4c6fb2220ac6705aa97046f3503a1/posts?after=1699369636979%2C27138103&appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=postV1&filterType=MOMENT_VIEWER&language=en&limit=1&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178210447&wmd=Y1OTRioyq7vF2%2FSYTL09CAraDDM%3D'
# 'https://global.apis.naver.com/weverse/wevweb/member/v1.1/community-36/artistMembers?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=artistMembersV1&filterType=MOMENT&language=en&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178123317&wmd=KHioIqTMvGRFPAxb3jUuMb0WdaE%3D'

def process_official_media(community_id):
    """
    Process the media https://weverse.io/fromis9/media?tab=all
    """
    posts = write_official_media(community_id)
    for p in posts:
        post_id = p['postId']
        date = utils.timestamp(p['publishedAt'])

        base_path = f'{get_media_path()}/officialMedia/{post_id}'

        if video := p['extension'].get('video'):
            video_id = video['videoId']
            path = f'{base_path}_{video_id}'

            if not p['membershipOnly']:
                download_extension_video(p, path)
            else:
                download_membership_video(video, post_id, path, date)

        if photos := p['extension'].get('image', {}).get('photos'):
            for photo in photos:
                url = photo['url']
                photo_id = photo['photoId']
                path = f'{base_path}_{photo_id}'
                utils.download_file(url, path, date)


def download_membership_video(video, post_id, path, date):
    if Path(path + '.mp4').exists():
        return

    video_id = video['videoId']

    base_path = f'{get_json_path()}/membership'

    mpd_path = Path(f'{base_path}/{post_id}_{video_id}.mpd')
    widevine_path = Path(f'{base_path}/{post_id}_{video_id}.xml')
    key_json_path = Path(f'{base_path}/{post_id}_{video_id}.key')

    if not key_json_path.exists() or True:
        key_json_path.parent.mkdir(parents=True, exist_ok=True)
        key_json = call_request(f'/video/v1.2/vod/{video_id}/inKey?drm=Widevine&securityLevelByTrack=true', post=True)

        key_json_path.write_text(json.dumps(key_json), encoding='utf-8')
    else:
        key_json = json.loads(key_json_path.read_text(encoding='utf-8'))

    key = key_json['inKey']

    if not widevine_path.exists() or True:
        print('Requesting vod playback')
        widevine_path.parent.mkdir(parents=True, exist_ok=True)

        infra_video_id = video['infraVideoId']

        api_call = f'https://apis.naver.com/neonplayer/vodplay/v3/playback/{infra_video_id}?key={key}&drm=Widevine'

        # Headers converted from the curl -H flags
        headers = {
            'accept': 'application/xml',
            'accept-language': 'en-AU,en;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://weverse.io',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://weverse.io/',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-storage-access': 'active',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        }

        response = requests.get(api_call, headers=headers)
        widevine_path.write_text(response.text, encoding='utf-8')
        widevine_xml = xmltodict.parse(response.text)
        print(widevine_xml)
    else:
        widevine_xml = xmltodict.parse(widevine_path.read_text(encoding='utf-8'))

    mpd_url = widevine_xml['MPD']['Period']['@xlink:href']

    if not mpd_path.exists() or True:
        mpd_path.parent.mkdir(parents=True, exist_ok=True)

        print(mpd_url)

        # Headers converted from the curl -H flags
        headers = {
            'accept': 'application/xml',
            'accept-language': 'en-AU,en;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://weverse.io',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://weverse.io/',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-storage-access': 'active',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        }

        print('Requesting mpd ', mpd_url)
        response = requests.get(mpd_url, headers=headers)
        mpd_path.write_text(response.text)
        mpd_text = response.text
        # print(mpd_text)
    else:
        mpd_text = mpd_path.read_text(encoding='utf-8')

    pssh = utils.get_pssh_from_mpd(mpd_text)

    # license_url = highest_qual['ContentProtection']['dashif:laurl']
    license_url = key_json['licenseUrl']

    download_widevine_video(mpd_url, pssh, license_url, path, date)


def get_browser_cookies(browser_name):
    # browser_name can be 'chrome', 'firefox', 'edge', 'opera', 'vivaldi', 'safari'
    ydl_opts = {'cookiefile': None, 'cookiesfrombrowser': (browser_name, None, None, None)}

    with YoutubeDL(ydl_opts) as ydl:
        # Extract cookies for the specific domain to keep it clean
        cookie_jar = ydl.cookiejar
        # Load cookies from the browser into the jar
        ydl.plugins_extractor = []  # We don't need extractors, just the jar

        # This triggers the internal yt-dlp cookie extraction logic
        # It handles decryption (DPAPI on Windows, etc.)
        cookies = {}
        for cookie in cookie_jar:
            # You can filter for specific domains if you want
            print(cookie.domain)
            if "weverse" in cookie.domain or "naver" in cookie.domain:
                cookies[cookie.name] = cookie.value
        return cookies


def get_keys(license_url, pssh_b64):
    print("[*] Generating License Challenge...")
    pssh = PSSH(pssh_b64)  # pywidevine handles b64 or hex automatically

    # Load your local WVD device
    device = Device.load(WVD_DEVICE_PATH)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()

    challenge = cdm.get_license_challenge(session_id, pssh)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
        "Origin": "https://weverse.io",
        "Referer": "https://weverse.io/",
        "Content-Type": "application/octet-stream",  # Standard for Widevine
    }

    print("[*] Requesting License from Naver...")
    licence = requests.post(license_url, data=challenge, headers=headers)
    licence.raise_for_status()

    if licence.status_code != 200:
        print(f"Error: License request failed with status {licence.status_code}")

    # parse the license response message received from the license server API
    cdm.parse_license(session_id, licence.content)

    # print keys
    keys = []
    for key in cdm.get_keys(session_id):
        print(f"[{key.type}] {key.kid.hex}:{key.key.hex()}")
        if key.type == 'CONTENT':
            key_str = f"{key.kid.hex}:{key.key.hex()}"
            keys.append(key_str)
            print(f"[+] Found Key: {key_str}")

    # finished, close the session, disposing of all keys and other related data
    cdm.close(session_id)

    return keys


def download_widevine_video(mpd_url, pssh_b64, license_url, output_path, date=None):
    """
    1. Gets Decryption Keys via PyWidevine
    2. Downloads encrypted streams via yt-dlp
    3. Decrypts via mp4decrypt
    4. Merges via ffmpeg
    """

    print('Download widevine: ')
    print('mpd:', mpd_url)
    print('pssh', pssh_b64)
    print('license', license_url)
    keys = get_keys(license_url, pssh_b64)

    if not keys:
        print("[-] No content keys found.")
        return

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- STEP 2: DOWNLOAD ENCRYPTED VIDEO/AUDIO ---
    print("[*] Downloading encrypted streams...")
    # We download video and audio separately to decrypt them individually
    video_enc = output_path.with_name(f"{output_path.stem}_enc.mp4")
    audio_enc = output_path.with_name(f"{output_path.stem}_enc.m4a")

    # Use yt-dlp to grab the best video and best audio
    subprocess.run(['yt-dlp', '-f', 'bestvideo', mpd_url, '-o', str(video_enc), '--allow-unplayable-formats'])
    subprocess.run(['yt-dlp', '-f', 'bestaudio', mpd_url, '-o', str(audio_enc), '--allow-unplayable-formats'])

    # --- STEP 3: DECRYPT ---
    print("[*] Decrypting...")
    video_dec = output_path.with_name(f"{output_path.stem}_dec.mp4")
    audio_dec = output_path.with_name(f"{output_path.stem}_dec.m4a")

    # Construct decryption command (supports multiple keys if present)
    decrypt_cmd_v = ['mp4decrypt']
    decrypt_cmd_a = ['mp4decrypt']
    for k in keys:
        decrypt_cmd_v.extend(['--key', k])
        decrypt_cmd_a.extend(['--key', k])

    decrypt_cmd_v.extend([str(video_enc), str(video_dec)])
    decrypt_cmd_a.extend([str(audio_enc), str(audio_dec)])

    subprocess.run(decrypt_cmd_v)
    subprocess.run(decrypt_cmd_a)

    # --- STEP 4: MERGE ---
    merged_path = output_path.with_suffix(".mp4")
    print(f"[*] Merging into {merged_path}...")
    subprocess.run([
        'ffmpeg', '-y',
        '-i', str(video_dec),
        '-i', str(audio_dec),
        '-c', 'copy', str(merged_path)
    ])

    if merged_path.exists():
        utils.edit_creation_date(merged_path, date)

    # Cleanup temp files
    for f in [video_enc, audio_enc, video_dec, audio_dec]:
        if f.exists():
            f.unlink()

    print("[+] Done!")


def process_lives(community_id):
    """
    Process the lives https://weverse.io/fromis9/live
    """
    write_live_tab_posts(community_id)

    live_posts = write_individual_posts(get_live_json_path(), f'{COMMUNITY_NAME}/{LIVE_POSTS_FOLDER}', WRITE_LIVE_COMMENTS)
    if DOWNLOAD_LIVE_VODS:
        for p in live_posts:
            post_id = p['postId']
            path = f'{get_media_path()}/lives/{post_id}'
            date = utils.timestamp(p['publishedAt'])

            if p['membershipOnly']:
                if video := p['extension'].get('video'):
                    download_membership_video(video, post_id, path, date)
                print(p)
            else:
                download_extension_video(p, path)


def process_member(member_json):
    """
    Don't need to grab posts here as they all should be parsed when calling `process_artist_posts`
    """

    member_id = member_json['memberId']
    member_name = member_json['artistOfficialProfile']['officialName']

    # profile
    req = f'/member/v1.0/member-{member_id}?fields=memberId%2CcommunityId%2Cjoined%2CprofileType%2CprofileName%2CprofileImageUrl%2CprofileCoverImageUrl%2CprofileComment%2CmyProfile%2Chidden%2Cblinded%2CmemberJoinStatus%2CfirstJoinAt%2CfollowCount%2Cfollowed%2ChasMembership%2ChasOfficialMark%2CartistOfficialProfile%2CavailableActions%2CprofileSpaceStatus%2Cbadges%2CshareUrl'
    profile_data = write_single(req, f'{get_json_path()}/member/{member_name}/profile.json', True)

    if DOWNLOAD_PROFILE_PICTURES:
        pics = [
            (profile_data.get('profileImageUrl'), 'profileImage'),
            (profile_data.get('profileCoverImageUrl'), 'profileCover'),
            (profile_data.get('artistOfficialProfile', {}).get('officialImageUrl'), 'profileOfficial'),
        ]

        for (pic_url, name) in pics:
            if pic_url:
                url_date = utils.get_url_date(pic_url)
                path = f'{get_media_path()}/member/{member_name}/profile/{name}_{url_date}'
                utils.download_file(pic_url, path)

    if WRITE_ARTIST_COMMENTS:
        # comments
        print('Downloading Member Comments: ', member_name)
        req = f'/comment/v1.0/member-{member_id}/comments?fieldSet=memberCommentsV1'
        write_paged_requests(req, req, f'{get_json_path()}/member/{member_name}/comments.json', True)

    # moments
    if DOWNLOAD_MOMENTS_JSON:
        print('Downloading Member Moments: ', member_name)
        req = f'/post/v1.0/member-{member_id}/posts?fieldSet=postsV1&filterType=MOMENT_VIEWER&limit=1'
        moments = write_paged_requests(req, req, f'{get_json_path()}/member/{member_name}/moments.json', True)

        if DOWNLOAD_MOMENTS_MEDIA:
            for m in moments:
                moment_id = m['postId']
                date = utils.timestamp(m['publishedAt'])

                if momentW1 := m['extension'].get('momentW1'):
                    # print('momentW1', m['summary']['videoCount'], m['summary']['photoCount'])
                    # print(momentW1)
                    if photo := momentW1.get('photo'):
                        image_url = photo['url']
                        utils.download_file(image_url, f'{get_media_path()}/member/{member_name}/moments/{moment_id}', date)
                else:
                    video_id = m['extension']['moment']['video']['videoId']
                    download_cvideo_json(video_id, f'{get_media_path()}/member/{member_name}/moments/{moment_id}', date)

                    image_url = m['extension']['moment']['video']['uploadInfo']['imageUrl']
                    utils.download_file(image_url, f'{get_media_path()}/member/{member_name}/moments/{moment_id}', date)


def process_members():
    artists = get_artists(COMMUNITY_ID)
    for a in artists:
        process_member(a)


def process_official_accounts():
    if len(official_channels) == 0:
        print('No official accounts set, fill in the `official_channels` list')

    for id in official_channels:
        req = f'/post/v1.0/member-{id}/posts'
        write_paged_requests(req, req, f'{get_json_path()}/official/{id}.json', True)


def process_artist_posts(community_id):
    """
    https://weverse.io/fromis9/artist
    """
    req = f'/post/v1.0/community-{community_id}/artistTabPosts'

    json_path = get_artist_json_path()

    write_paged_requests(req, req, json_path, True)

    posts = write_individual_posts(json_path, f'{COMMUNITY_NAME}/{ARTIST_POSTS_FOLDER}', WRITE_POST_COMMENTS)

    if DOWNLOAD_POST_MEDIA:
        for p in posts:
            post_id = p['postId']

            date = utils.timestamp(p['publishedAt'])

            author = p['author']['artistOfficialProfile']['officialName']

            # download post images
            if photos := p['attachment'].get('photo'):
                for photo_id, content in photos.items():
                    photo_url = content['url']

                    path = f'{get_media_path()}/artistPosts/{author}/{post_id}_{photo_id}'
                    # print('Downloading photo', path, photo_url)
                    if utils.download_file(photo_url, path, date):
                        time.sleep(1)

            if videos := p['attachment'].get('video'):
                for video_id, content in videos.items():
                    path = f'{get_media_path()}/artistPosts/{author}/{post_id}_{video_id}'
                    download_cvideo_json(video_id, path, date)


def process_dms():
    # TODO this doesn't work
    req = '/dm/v2.0/my/rooms'
    all_rooms = write_single(req, f'{get_json_path()}/dm/rooms.json', True)
    # print(room_json)

    for room in all_rooms['rooms']:
        room_id = room['roomId']
        print(room)

        # '/dm/v2.0/messages?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&language=en&os=WEB&platform=WEB&prev=9223372036854775807&roomId=WR3OBRZ&transLang=en&wpf=pc&wmd=PifF4TXK5row%2BIkZIcZHUuGxGck%3D&wmsgpad=1773715693733'
        req = f'/dm/v2.0/messages?roomId={room_id}'
        write_paged_requests(req, req, f'{get_json_path()}/dm/{room_id}.json', False)
        return


def set_community_id(community_name):
    global COMMUNITY_ID
    global COMMUNITY_NAME

    req = f'/community/v1.0/communityIdUrlPathByUrlPathArtistCode?keyword={community_name}'
    resp = write_single(req, f'{get_json_path()}/communityId.json')

    COMMUNITY_ID = resp['communityId']
    COMMUNITY_NAME = community_name

    return resp


def process_community():
    req = f'/community/v1.0/community-{COMMUNITY_ID}?fieldSet=communityHomeV1_1'
    # print(req)
    # print(call_request(req))
    resp = write_single(req, f'{get_json_path()}/communityHome.json', True)
    print(resp)

    values = { 'logoImage', 'homeHeaderImage', 'webHomeHeaderImage', }
    base_path = f'{get_media_path()}/community/'

    for v in values:
        if url := resp.get(v):
            url_date = utils.get_url_date(url)
            path = f'{base_path}/{v}_{url_date}'
            utils.download_file(url, path)

    # TODO download agency profile?

def download_community(community_name):
    set_community_id(community_name)
    
    process_community()
    
    process_members()
    process_lives(COMMUNITY_ID)
    process_artist_posts(COMMUNITY_ID)
    process_official_media(COMMUNITY_ID)

    process_official_accounts()
    # process_dms()


def download():
    download_community('fromis9')
    # download_community('ahnbohyun')

if __name__ == '__main__':
    download()
