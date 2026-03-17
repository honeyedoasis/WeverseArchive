import datetime
import json
from pathlib import Path

import yt_dlp
import time
import xmltodict

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
DOWNLOAD_LIVE_VODS = True  # this one will take forever to process
DOWNLOAD_POST_MEDIA = True # this doesn't work for videos atm
DOWNLOAD_PROFILE_PICTURES = True
DOWNLOAD_OFFICIAL_MEDIA = False # The media in this tab https://weverse.io/fromis9/media?tab=all

PAGED_SLEEP = 10
SHORT_SLEEP = 0.5

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
        time.sleep(PAGED_SLEEP)

    # Clean up state file if finished
    state_path = Path(f"{filename}.state")
    if state_path.exists():
        state_path.unlink()
    print(f"Finished {filename}")
    return out_data


def call_request(req):
    extr = make_extractor()
    resp = run_extr(extr, req)
    time.sleep(SHORT_SLEEP)
    return resp


def write_single(req, filename, skip_exists=True):
    file_path = Path(f'{filename}')
    if skip_exists and file_path.exists():
        return json.loads(file_path.read_text(encoding='utf-8'))

    extr = make_extractor()
    data = run_extr(extr, req)

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
        data = write_single(req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/{folder}/{post_id}.json', True)
        # print(data)

        out_data.append(data)

        if write_comments:
            print(f'Writing post comments {post_id}')
            req = f'/comment/v1.0/post-{post_id}/comments?fieldSet=postCommentsV1'
            write_paged_requests(req, req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/{folder}/{post_id}.comments.json', True, True)

    return out_data


def download_live_vod(data):
    # TODO maybe just use yt-dlp?
    video_id = data['extension']['video']['videoId']
    post_id = data['postId']
    date = utils.timestamp(data['publishedAt'])

    if data['membershipOnly']:
        print('Skip downloading membership video ', video_id)
        return

    vod_data = get_vod_video_json(video_id)
    url = get_vod_url(vod_data)
    filepath = f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/vod/{post_id}'
    print('Downloading vod ', post_id)
    utils.download_file(url, filepath, date)


def write_live_chat():
    posts = []

    with open(f'{COMMUNITY_NAME}/{JSON_FOLDER}/all_live_posts.json', 'r', encoding='utf-8') as file:
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
        write_paged_requests(req, req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/liveChat/{postId}.json', True, True)
        time.sleep(5)


def write_media(community_id):
    req = f'/media/v1.0/community-{community_id}/searchAllMedia?fieldSet=postsV1'
    return write_paged_requests(req, req, MEDIA_JSON, True)


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
    write_paged_requests(req, req, LIVE_POSTS_JSON, True)

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
    if data := write_single(req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/artistProfiles.json', skip_exists=True):
        return data['artistProfiles']

    print('Error failed to get artists')
    return None


# 'https://global.apis.naver.com/weverse/wevweb/post/v1.0/member-67b4c6fb2220ac6705aa97046f3503a1/posts?after=1699369636979%2C27138103&appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=postV1&filterType=MOMENT_VIEWER&language=en&limit=1&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178210447&wmd=Y1OTRioyq7vF2%2FSYTL09CAraDDM%3D'
# 'https://global.apis.naver.com/weverse/wevweb/member/v1.1/community-36/artistMembers?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=artistMembersV1&filterType=MOMENT&language=en&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178123317&wmd=KHioIqTMvGRFPAxb3jUuMb0WdaE%3D'

def process_media(community_id):
    """
    Process the media https://weverse.io/fromis9/media?tab=all
    """
    posts = write_media(community_id)
    for p in posts:
        post_id = p['postId']
        print(p)


def process_lives(community_id):
    """
    Process the lives https://weverse.io/fromis9/live
    """
    write_live_tab_posts(community_id)

    vods = write_individual_posts(LIVE_POSTS_JSON, LIVE_POSTS_FOLDER, WRITE_LIVE_COMMENTS)
    if DOWNLOAD_LIVE_VODS:
        for v in vods:
            download_live_vod(v)


def process_member(member_json):
    """
    Don't need to grab posts here as they all should be parsed when calling `process_artist_posts`
    """

    member_id = member_json['memberId']
    member_name = member_json['artistOfficialProfile']['officialName']

    # profile
    req = f'/member/v1.0/member-{member_id}?fields=memberId%2CcommunityId%2Cjoined%2CprofileType%2CprofileName%2CprofileImageUrl%2CprofileCoverImageUrl%2CprofileComment%2CmyProfile%2Chidden%2Cblinded%2CmemberJoinStatus%2CfirstJoinAt%2CfollowCount%2Cfollowed%2ChasMembership%2ChasOfficialMark%2CartistOfficialProfile%2CavailableActions%2CprofileSpaceStatus%2Cbadges%2CshareUrl'
    profile_data = write_single(req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/member/{member_name}/profile.json', True)

    if DOWNLOAD_PROFILE_PICTURES:
        pics = [
            (profile_data.get('profileImageUrl'), 'profileImage'),
            (profile_data.get('profileCoverImageUrl'), 'profileCover'),
            (profile_data.get('artistOfficialProfile', {}).get('officialImageUrl'), 'profileOfficial'),
        ]

        for (pic_url, name) in pics:
            if pic_url:
                utils.download_file(pic_url, f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/member/{member_name}/profile/{name}')

    if WRITE_ARTIST_COMMENTS:
        # comments
        print('Downloading Member Comments: ', member_name)
        req = f'/comment/v1.0/member-{member_id}/comments?fieldSet=memberCommentsV1'
        write_paged_requests(req, req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/member/{member_name}/comments.json', True)

    # moments
    if DOWNLOAD_MOMENTS_JSON:
        print('Downloading Member Moments: ', member_name)
        req = f'/post/v1.0/member-{member_id}/posts?fieldSet=postsV1&filterType=MOMENT_VIEWER&limit=1'
        moments = write_paged_requests(req, req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/member/{member_name}/moments.json', True)

        if DOWNLOAD_MOMENTS_MEDIA:
            for m in moments:
                moment_id = m['postId']
                date = utils.timestamp(m['publishedAt'])

                if momentW1 := m['extension'].get('momentW1'):
                    # print('momentW1', m['summary']['videoCount'], m['summary']['photoCount'])
                    # print(momentW1)
                    if photo := momentW1.get('photo'):
                        image_url = photo['url']
                        utils.download_file(image_url, f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/member/{member_name}/moments/{moment_id}', date)
                else:
                    video_id = m['extension']['moment']['video']['videoId']
                    download_cvideo_json(video_id, f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/member/{member_name}/moments/{moment_id}', date)

                    image_url = m['extension']['moment']['video']['uploadInfo']['imageUrl']
                    utils.download_file(image_url, f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/member/{member_name}/moments/{moment_id}', date)


def process_members():
    artists = get_artists(COMMUNITY_ID)
    for a in artists:
        process_member(a)


def process_official_accounts():
    if len(official_channels) == 0:
        print('No official accounts set, fill in the `official_channels` list')

    for id in official_channels:
        req = f'/post/v1.0/member-{id}/posts'
        write_paged_requests(req, req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/official/{id}.json', True)


def process_artist_posts(community_id):
    """
    https://weverse.io/fromis9/artist
    """
    req = f'/post/v1.0/community-{community_id}/artistTabPosts'
    write_paged_requests(req, req, ARTIST_POSTS_JSON, True)
    posts = write_individual_posts(ARTIST_POSTS_JSON, ARTIST_POSTS_FOLDER, WRITE_POST_COMMENTS)

    if DOWNLOAD_POST_MEDIA:
        for p in posts:
            post_id = p['postId']

            date = utils.timestamp(p['publishedAt'])

            author = p['author']['artistOfficialProfile']['officialName']

            # download post images
            if photos := p['attachment'].get('photo'):
                for photo_id, content in photos.items():
                    photo_url = content['url']

                    path = f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/artistPosts/{author}/{post_id}_{photo_id}'
                    # print('Downloading photo', path, photo_url)
                    if utils.download_file(photo_url, path, date):
                        time.sleep(1)

            if videos := p['attachment'].get('video'):
                for video_id, content in videos.items():
                    path = f'{COMMUNITY_NAME}/{MEDIA_FOLDER}/artistPosts/{author}/{post_id}_{video_id}'
                    download_cvideo_json(video_id, path, date)


def process_dms():
    # TODO this doesn't work
    req = '/dm/v2.0/my/rooms'
    all_rooms = write_single(req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/dm/rooms.json', True)
    # print(room_json)

    for room in all_rooms['rooms']:
        room_id = room['roomId']
        print(room)

        # '/dm/v2.0/messages?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&language=en&os=WEB&platform=WEB&prev=9223372036854775807&roomId=WR3OBRZ&transLang=en&wpf=pc&wmd=PifF4TXK5row%2BIkZIcZHUuGxGck%3D&wmsgpad=1773715693733'
        req = f'/dm/v2.0/messages?roomId={room_id}'
        write_paged_requests(req, req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/dm/{room_id}.json', False)


def set_community_id(community_name):
    global COMMUNITY_ID
    global COMMUNITY_NAME

    req = f'/community/v1.0/communityIdUrlPathByUrlPathArtistCode?keyword={community_name}'
    resp = write_single(req, f'{COMMUNITY_NAME}/{JSON_FOLDER}/communityId.json')

    COMMUNITY_ID = resp['communityId']
    COMMUNITY_NAME = community_name

    return resp

def download_community(community_name):
    set_community_id(community_name)

    process_members()
    process_lives(COMMUNITY_ID)
    process_artist_posts(COMMUNITY_ID)
    # process_media(COMMUNITY_ID)

    process_official_accounts()
    process_dms()


def download():
    download_community('fromis9')


if __name__ == '__main__':
    download()
