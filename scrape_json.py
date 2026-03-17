import datetime
import json
from pathlib import Path

import yt_dlp
import time

from yt_dlp.extractor.weverse import WeverseIE
from yt_dlp.utils import ExtractorError

import utils

COMMUNITY_ID = 36

MEDIA_FOLDER = 'media'
JSON_FOLDER = 'json-data'

MEDIA_JSON = f'{JSON_FOLDER}/searchAllMedia.json'

LIVE_POSTS_JSON = f'{JSON_FOLDER}/liveTabPosts.json'
LIVE_POSTS_FOLDER = 'liveTabPosts'

ARTIST_POSTS_JSON = f'{JSON_FOLDER}/artistTabPosts.json'
ARTIST_POSTS_FOLDER = 'artistTabPosts'

WRITE_POST_COMMENTS = False
WRITE_LIVE_COMMENTS = False
WRITE_ARTIST_COMMENTS = False

DOWNLOAD_MOMENTS_JSON = True
DOWNLOAD_MOMENTS_MEDIA = True

# members = {
#     'jiheon': '5fb309bc7489a576484431ba8338807e',  # jh
#     'hayoung': '67b4c6fb2220ac6705aa97046f3503a1',  # hy
#     'chaeyoung': '65eff6ab044ae8dea6816794f11a6fc1',  # cy
#     'jiwon': '6599dbbcaa26237c2ab0f3becb421b45',  # jw
#     'jisun': '01435f74a49ba8a519705ad242348232',  # js
#     'saerom': '326c0d1e7045798aa3964e2028c34628',  # sr
#     'seoyeon': '56bdfafb606d9ce1b4ecdd572595e242',  # sy
#     'nagyung': '5477d46be848bd40252f9d13ef62cb4d',  # ng
#     'gyuri': 'db56036fc59a94a9ef617261c90c783f'  # gr
# }

# What is this for?
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
    '58afde0dbc1fccd94cd44eff91fa3673'  # floverse_9
    # '4e3e72a5b2ea6ad2c3ac319a4dbc26d0', # Weverse
]

ydl_params = {
    # 'verbose': True,
    'quiet': True,
    'cookiesfrombrowser': ('firefox',),
}

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
        return json.loads(state_path.read_text(encoding='utf-8'))
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
        time.sleep(5)

    # Clean up state file if finished
    state_path = Path(f"{filename}.state")
    if state_path.exists():
        state_path.unlink()
    print(f"Finished {filename}")


def call_request(req):
    extr = make_extractor()
    return run_extr(extr, req)


def write_single(req, filename, skip_exists=True):
    file_path = Path(f'{filename}')
    if skip_exists and file_path.exists():
        return json.loads(file_path.read_text(encoding='utf-8'))

    extr = make_extractor()
    data = run_extr(extr, req)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=4), encoding='utf-8')

    return data


def write_individual_posts(post_file, folder, write_comments=False):
    posts = []

    with open(post_file, 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            posts.append(data['postId'])

    for post_id in posts:
        req = f'/post/v1.0/post-{post_id}?fieldSet=postV1'
        write_single(req, f'{JSON_FOLDER}/{folder}/{post_id}.json', True)

        if write_comments:
            print(f'Writing post comments {post_id}')
            req = f'/comment/v1.0/post-{post_id}/comments?fieldSet=postCommentsV1'
            write_paged_requests(req, req, f'{JSON_FOLDER}/{folder}/{post_id}.comments.json', True, True)


def write_live_chat():
    posts = []

    with open(f'{JSON_FOLDER}/all_live_posts.json', 'r', encoding='utf-8') as file:
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
        write_paged_requests(req, req, f'{JSON_FOLDER}/liveChat/{postId}.json', True, True)
        time.sleep(5)


def write_media(community_id):
    req = f'/media/v1.0/community-{community_id}/searchAllMedia?fieldSet=postsV1'
    write_paged_requests(req, req, MEDIA_JSON, True)


def get_video_json(video_id):
    # whats this for lives?
    req = f'/video/v2.1/vod/{video_id}/playInfo?version=v2'
    return write_single(req, f'{JSON_FOLDER}/videos/{video_id}.json', True)


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
    write_paged_requests(req, req, LIVE_POSTS_JSON, True)

    if True:
        print('Bla')
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
    if data := write_single(req, f'{JSON_FOLDER}/artistProfiles.json', skip_exists=True):
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


def process_member(member_id):
    """
    Don't need to grab posts here as they all should be parsed when calling `process_artist_posts`
    """
    # profile
    req = f'/member/v1.0/member-{member_id}?fields=memberId%2CcommunityId%2Cjoined%2CprofileType%2CprofileName%2CprofileImageUrl%2CprofileCoverImageUrl%2CprofileComment%2CmyProfile%2Chidden%2Cblinded%2CmemberJoinStatus%2CfirstJoinAt%2CfollowCount%2Cfollowed%2ChasMembership%2ChasOfficialMark%2CartistOfficialProfile%2CavailableActions%2CprofileSpaceStatus%2Cbadges%2CshareUrl'
    write_single(req, f'{JSON_FOLDER}/artist/{member_id}/profile.json', True)

    if WRITE_ARTIST_COMMENTS:
        # comments
        print('Downloading Member Comments: ', member_id)
        req = f'/comment/v1.0/member-{member_id}/comments?fieldSet=memberCommentsV1'
        write_paged_requests(req, req, f'{JSON_FOLDER}/artist/{member_id}/comments.json', True)

    # moments
    if DOWNLOAD_MOMENTS_JSON:
        print('Downloading Member Moments: ', member_id)
        req = f'/post/v1.0/member-{member_id}/posts?fieldSet=postsV1&filterType=MOMENT_VIEWER&limit=1'
        moments = write_paged_requests(req, req, f'{JSON_FOLDER}/artist/{member_id}/moments.json', True)

        if DOWNLOAD_MOMENTS_MEDIA:
            for m in moments:
                video_id = m['extension']['moment']['video']['videoId']
                moment_id = m['postId']
                date = utils.timestamp(m['publishedAt'])
                download_cvideo_json(video_id, f'{MEDIA_FOLDER}/{member_id}/moments/{moment_id}', date)


def process_members():
    artists = get_artists(COMMUNITY_ID)
    for a in artists:
        member_id = a['memberId']
        process_member(member_id)


def process_official_accounts():
    for id in official_channels:
        req = f'/post/v1.0/member-{id}/posts'
        write_paged_requests(req, req, f'{JSON_FOLDER}/official/{id}.json', True)


def process_artist_posts(community_id):
    """
    https://weverse.io/fromis9/artist
    """
    req = f'/post/v1.0/community-{community_id}/artistTabPosts'
    write_paged_requests(req, req, ARTIST_POSTS_JSON, True)
    write_individual_posts(ARTIST_POSTS_JSON, ARTIST_POSTS_FOLDER, WRITE_POST_COMMENTS)


def process_dms():
    req = '/dm/v2.0/my/rooms'
    all_rooms = write_single(req, f'{JSON_FOLDER}/dm/rooms.json', True)
    # print(room_json)

    for room in all_rooms['rooms']:
        room_id = room['roomId']
        print(room)

        # TODO why doesn't this work
        # '/dm/v2.0/messages?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&language=en&os=WEB&platform=WEB&prev=9223372036854775807&roomId=WR3OBRZ&transLang=en&wpf=pc&wmd=PifF4TXK5row%2BIkZIcZHUuGxGck%3D&wmsgpad=1773715693733'
        req = f'/dm/v2.0/messages?roomId={room_id}'
        write_paged_requests(req, req, f'{JSON_FOLDER}/dm/{room_id}.json', False)


def download():
    process_members()
    # process_lives(COMMUNITY_ID)
    # process_artist_posts(COMMUNITY_ID)
    # process_dms()


if __name__ == '__main__':
    download()
    # print(download_cvideo_json('1-491837', 'test_vid'))
