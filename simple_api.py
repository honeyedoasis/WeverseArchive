import datetime
import json
from pathlib import Path

import yt_dlp
import time

from yt_dlp.extractor.weverse import WeverseIE
from yt_dlp.utils import ExtractorError

MEDIA_JSON = 'json-data/searchAllMedia.json'

LIVE_POSTS_JSON = 'json-data/liveTabPosts.json'
LIVE_POSTS_FOLDER = 'liveTabPosts'

ARTIST_POSTS_JSON = 'json-data/artistTabPosts.json'
ARTIST_POSTS_FOLDER = 'artistTabPosts'

WRITE_POST_COMMENTS = False
WRITE_LIVE_COMMENTS = True

members = {
    'jiheon': '5fb309bc7489a576484431ba8338807e',  # jh
    'hayoung': '67b4c6fb2220ac6705aa97046f3503a1',  # hy
    'chaeyoung': '65eff6ab044ae8dea6816794f11a6fc1',  # cy
    'jiwon': '6599dbbcaa26237c2ab0f3becb421b45',  # jw
    'jisun': '01435f74a49ba8a519705ad242348232',  # js
    'saerom': '326c0d1e7045798aa3964e2028c34628',  # sr
    'seoyeon': '56bdfafb606d9ce1b4ecdd572595e242',  # sy
    'nagyung': '5477d46be848bd40252f9d13ef62cb4d',  # ng
    'gyuri': 'db56036fc59a94a9ef617261c90c783f'  # gr
}

rooms = {
    'jiheon': '414361',  # jh
    'hayoung': '297243',  # hy
    'chaeyoung': '329164',  # cy
    'jiwon': '464268',  # jw
    'jisun': '221087',  # js
    'saerom': '321529',  # sr
    'seoyeon': '229217',  # sy
    'nagyung': '233441',  # ng
}

"""
Get this by finding the profile of the official channel
Example: https://weverse.io/fromis9/profile/58afde0dbc1fccd94cd44eff91fa3673
"""
official_channels = [
    # '47b84d66038c899cfc87e38df8b92143', # fromis_9
    '58afde0dbc1fccd94cd44eff91fa3673' # floverse_9
    # '4e3e72a5b2ea6ad2c3ac319a4dbc26d0', # Weverse
]

params = {
    # 'verbose': True,
    'quiet': True,
    'cookiesfrombrowser': ('firefox',),
}

def make_extractor():
    ydl = yt_dlp.YoutubeDL(params)

    ext = WeverseIE()
    ext.set_downloader(ydl)
    ext.initialize()
    return ext

def get_next_page(json_data):
    paging = json_data['paging']
    if param := paging.get('nextParams'):
        return param['after'] # .replace(',', '%2C')

    return None

def get_prev_page(json_data):
    paging = json_data['paging']
    if param := paging.get('previousParams'):
        if prev := param.get('prev'):
            return prev #.replace(',', '%2C')

        if prev := param.get('before'):
            return prev #.replace(',', '%2C')

        # FAILED TO FIND PREV PAGE?
        breakpoint()

    return None

def run_extr(extr, req, out_data=None, grab_data=True):
    print(req)

    while True:
        try:
            json_data = extr._call_api(req, '')
            print(json_data)
            break
        except Exception as e:
            print(e)
            breakpoint()
            time.sleep(5.0)

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
        return json.loads(state_path.read_text())
    return None

def save_resume_state(filename, cursor, processed_indices=None):
    """Helper to save the current cursor/progress state."""
    state_path = Path(f"{filename}.state")
    state = {"cursor": cursor, "processed_indices": processed_indices or []}
    state_path.write_text(json.dumps(state))

def write_paged_requests(req, initial_req, filename, use_after, skip_exists=False):
    """
    Processes paginated requests.
    Saves the 'after' or 'prev' cursor to a .state file to resume.
    """
    file_path = Path(filename)
    if skip_exists and file_path.exists():
        print(f"File {filename} exists, skipping.")
        return

    out_data = []
    current_cursor = None

    # Resume logic
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                out_data = json.load(f)
            state = get_resume_state(filename)
            if state:
                current_cursor = state.get("cursor")
                print(f"Resuming {filename} from cursor: {current_cursor}")
            else:
                print(f"{file_path} exists but no state found, skipping")
                return
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
        time.sleep(5)

    # Clean up state file if finished
    state_path = Path(f"{filename}.state")
    if state_path.exists():
        state_path.unlink()
    print(f"Finished {filename}")

def debug_api(req):
    extr = make_extractor()
    return run_extr(extr, req)

def write_single(req, filename, skip_exists=True):
    file_path = Path(f'{filename}')
    if skip_exists and file_path.exists():
        return json.loads(file_path.read_text())

    extr = make_extractor()
    data = run_extr(extr, req)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=4), encoding='utf-8')

    return data

def write_multiple(reqs, filename, grab_data, skip_exists=False):
    """
    Processes a list of requests.
    Skips requests that have already been indexed in the state file.
    """
    file_path = Path(filename)
    out_data = []
    processed_indices = []

    # Resume logic: Load existing data and progress state
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                out_data = json.load(f)
            state = get_resume_state(filename)
            if state:
                processed_indices = state.get("processed_indices", [])
                print(f"Resuming {filename}: {len(processed_indices)} requests already processed.")
        except Exception as e:
            print(f"Error loading existing file: {e}. Starting fresh.")

    extr = make_extractor()

    for i, req in enumerate(reqs):
        # Skip if this index was already completed
        if i in processed_indices:
            continue

        print(f"Processing ({i + 1}/{len(reqs)}): {req}")
        try:
            # Note: run_extr modifies out_data in place based on your original code
            run_extr(extr, req, out_data, grab_data)

            # Record progress
            processed_indices.append(i)

            # Write to disk immediately
            save_progress(filename, out_data)
            save_resume_state(filename, None, processed_indices)

            time.sleep(2.0)
        except Exception as e:
            print(f"Error on request {i}: {e}")
            break  # Stop loop but progress is saved

    # Clean up state file if finished
    if len(processed_indices) == len(reqs):
        state_path = Path(f"{filename}.state")
        if state_path.exists(): state_path.unlink()

def write_individual_posts(post_file, folder, write_comments=False):
    posts = []

    with open(post_file, 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            posts.append(data['postId'])

    for post_id in posts:
        req = f'/post/v1.0/post-{post_id}?fieldSet=postV1'
        write_single(req, f'json-data/{folder}/{post_id}.json', True)

        if write_comments:
            print(f'Writing post comments {post_id}')
            req = f'/comment/v1.0/post-{post_id}/comments?fieldSet=postCommentsV1'
            write_paged_requests(req, req, f'json-data/{folder}/{post_id}.comments.json', True, True)

def write_all_post_media():
    posts = []

    with open(f'json-data/searchAllMedia.json', 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            posts.append(data['postId'])

    # posts = [f'/post/v1.0/post-{p}?fieldSet=postV1' for p in posts]
    # posts = posts[:5]
    # for p in posts:
    #     print(p)
    # ['/post/v1.0/post-0-152103623?fieldSet=postV1', '/post/v1.0/post-4-104688875?fieldSet=postV1']
    # write_multiple(posts, 'json-data/AllMedia', False)

    for i, p in enumerate(posts):
        req = f'/post/v1.0/post-{p}?fieldSet=postV1'
        if write_single(req, f'json-data/media/{p}', True):
            print(i, '/', len(posts))
            time.sleep(3)

def write_live_chat():
    posts = []

    with open(f'json-data/all_live_posts.json', 'r', encoding='utf-8') as file:
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
        write_paged_requests(req, req, f'json-data/liveChat/{postId}.json', True, True)
        time.sleep(5)

# def write_post_comments(json_file):
#     with open(f'json-data/all_live_posts.json', 'r', encoding='utf-8') as file:
#         json_data = json.load(file)
#         for data in json_data:
#             post_id = data['postId']
#             print('downloading', post_id)
#             req = f'/comment/v1.0/post-{post_id}/comments?fieldSet=postCommentsV1'
#             write_paged_requests(req, req, f'json-data/allComments/{post_id}.json', True, True)
#             time.sleep(5)

def write_media(community_id):
    req = f'/media/v1.0/community-{community_id}/searchAllMedia?fieldSet=postsV1'
    write_paged_requests(req, req, MEDIA_JSON, True)

    # req = '/media/v1.0/community-36/searchAllMedia?fieldSet=postsV1'
    # write_all_requests(req, req, 'json-data/new_searchAllMedia.json', True)

def write_live_tab_posts(community_id):
    req = f'/post/v1.0/community-{community_id}/liveTabPosts'
    write_paged_requests(req, req, LIVE_POSTS_JSON, True)

def get_artists(community_id):
    req = f'/artistpedia/v1.0/community-{community_id}/highlight'
    if data := write_single(req, 'json-data/artistProfiles.json', skip_exists=True):
        return data['artistProfiles']

    print('Error failed to get artists')
    return None

# 'https://global.apis.naver.com/weverse/wevweb/post/v1.0/member-67b4c6fb2220ac6705aa97046f3503a1/posts?after=1699369636979%2C27138103&appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=postV1&filterType=MOMENT_VIEWER&language=en&limit=1&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178210447&wmd=Y1OTRioyq7vF2%2FSYTL09CAraDDM%3D'
# 'https://global.apis.naver.com/weverse/wevweb/member/v1.1/community-36/artistMembers?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=artistMembersV1&filterType=MOMENT&language=en&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178123317&wmd=KHioIqTMvGRFPAxb3jUuMb0WdaE%3D'

def process_media(community_id):
    """
    Process the media https://weverse.io/fromis9/media?tab=all
    """
    write_media(community_id)


def process_lives(community_id):
    """
    Process the lives https://weverse.io/fromis9/live
    """
    write_live_tab_posts(community_id)
    write_individual_posts(LIVE_POSTS_JSON, LIVE_POSTS_FOLDER, WRITE_LIVE_COMMENTS)

def process_member(m):
    """
    Don't need to grab posts here as they all should be parsed when calling `process_artist_posts`
    """

    # comments
    req = f'comment/v1.0/member-{m}/comments'
    write_paged_requests(req, req, f'json-data/artist/{m}/comments.json', True)

    # moments
    req = f'/post/v1.0/member-{id}/posts?fieldSet=postsV1&filterType=MOMENT_VIEWER&limit=1'
    write_paged_requests(req, req, f'json-data/artist/{m}/moments.json', True)

def process_official_accounts():
    for id in official_channels:
        req = f'/post/v1.0/member-{id}/posts'
        write_paged_requests(req, req, f'json-data/official/{id}.json', True)

def process_artist_posts(community_id):
    """
    https://weverse.io/fromis9/artist
    """
    req = f'/post/v1.0/community-{community_id}/artistTabPosts'
    write_paged_requests(req, req, ARTIST_POSTS_JSON, True)
    write_individual_posts(ARTIST_POSTS_JSON, ARTIST_POSTS_FOLDER, WRITE_POST_COMMENTS)

def download():
    COMMUNITY_ID = 36
    # print(get_artists(COMMUNITY_ID))
    # process_lives(COMMUNITY_ID)
    process_artist_posts(COMMUNITY_ID)


if __name__ == '__main__':
    write_individual_posts(ARTIST_POSTS_JSON, ARTIST_POSTS_FOLDER, WRITE_POST_COMMENTS)
    # download()

# write_all_comments()