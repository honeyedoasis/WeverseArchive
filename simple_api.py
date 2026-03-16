import datetime
import json
import os.path
from pathlib import Path

import yt_dlp
import time

from yt_dlp.extractor.weverse import WeverseIE
from yt_dlp.utils import ExtractorError

# import xmltodict

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

official_channels = [
    # '47b84d66038c899cfc87e38df8b92143',
    '58afde0dbc1fccd94cd44eff91fa3673'
    # '4e3e72a5b2ea6ad2c3ac319a4dbc26d0',
    # '58afde0dbc1fccd94cd44eff91fa3673'
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


def write_all_requests(req, initial_req, filename, use_after, skip_exists=False):
    file_path = Path(filename)

    if skip_exists:
        if file_path.exists():
            return

    extr = make_extractor()

    out_data = []

    next_page = None

    prev = None
    after = None

    # ids = set()

    initial = initial_req

    count = 0

    while True:
        mod_req = req

        if initial:
            mod_req = initial
            initial = None

        if use_after and after:
            mod_req += f'?after={after}'
        elif not use_after and prev:
            mod_req += f'?prev={prev}'

        print(req)

        # req = '/post/v1.0/community-36/artistTabPosts?fieldSet=postsV1'
        data = run_extr(extr, mod_req, out_data)
        # print(data)
        prev = get_prev_page(data)
        after = get_next_page(data)

        # for d in data['data']:
        #     ids.add(d['postId'])
        # print(len(ids))
        # print(paging)

        # new_msgs = []
        # # print('Data', len(data['data']))
        # for msg in data['data']:
        #     msg_id = int(msg['messageId'])
        #     if msg_id in messages:
        #         continue
        #
        #     messages.add(msg_id)
        #     new_msgs.append(msg)

        # print('New msgs', len(new_msgs))
        #     # body = msg['body']
        #     # print('Body', len(body))
        #     for b in msg['body']:
        #         print(b['value'])

        if use_after and not after:
            break
        elif not use_after and not prev:
            break
        # if not paging.get('after'):
        #     break
        print('waiting...')
        time.sleep(20)

        count += 1
        if count >= 2:
            break

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(out_data, indent=4), encoding='utf-8')

def debug_api(req):
    extr = make_extractor()
    return run_extr(extr, req)

def write_single(req, filename, skip_exists=True):
    file_path = Path(f'{filename}')
    if skip_exists and file_path.exists():
        return False

    extr = make_extractor()
    data = run_extr(extr, req)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=4), encoding='utf-8')

    return data


def write_multiple(reqs, filename, grab_data, skip_exists=True):
    file_path = Path(f'{filename}')
    if skip_exists and file_path.exists():
        return False

    out_data = []
    for req in reqs:
        extr = make_extractor()
        try:
            run_extr(extr, req, out_data, grab_data)
        except Exception as e:
            print(e)
            break
        time.sleep(2.0)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(out_data, indent=4), encoding='utf-8')

def write_all_live_posts():
    posts = []

    with open(f'json-data/liveTabPosts.json', 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            posts.append(data['postId'])

    posts = [f'/post/v1.0/post-{p}?fieldSet=postV1' for p in posts]
    posts = posts[:5]
    # for p in posts:
    #     print(p)
    # ['/post/v1.0/post-0-152103623?fieldSet=postV1', '/post/v1.0/post-4-104688875?fieldSet=postV1']
    write_multiple(posts, 'json-data/all_live_posts.json', False)

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


def write_all_live_comments():
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

    posts = posts[:5]
    for chatId, data in posts:
        postId = data['postId']
        req = f'/chat/v1.0/chat-{chatId}/artistMessages'
        print(req, postId, data['shareUrl'])
        write_all_requests(req, req, f'json-data/liveChat/{postId}.json', True, True)
        time.sleep(5)

def write_all_comments():
    posts = []
    with open(f'json-data/all_live_posts.json', 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        for data in json_data:
            post_id = data['postId']
            print('downloading', post_id)
            req = f'/comment/v1.0/post-{post_id}/comments?fieldSet=postCommentsV1'
            write_all_requests(req, req, f'json-data/allComments/{post_id}.json', True, True)
            time.sleep(5)

def gen_json_moments():
    for m, id in members.items():
        req = f'/post/v1.0/member-{id}/posts?fieldSet=postsV1&filterType=MOMENT_VIEWER&limit=1'
        write_all_requests(req, req, f'json-data/moments/{m}.json', True)

def gen_json_official_posts():
    for m in official_channels:
        req = f'/post/v1.0/member-{m}/posts'
        write_all_requests(req, req, f'json-data/official/{m}.json', True)


def write_all_posts(community_id):
    req = f'/media/v1.0/community-{community_id}/searchAllMedia?fieldSet=postsV1'
    write_all_requests(req, req, 'json-data/all_posts.json', True)

    # req = '/media/v1.0/community-36/searchAllMedia?fieldSet=postsV1'
    # write_all_requests(req, req, 'json-data/new_searchAllMedia.json', True)

def write_live_tab_posts(community_id):
    req = f'/post/v1.0/community-{community_id}/liveTabPosts'
    write_all_requests(req, req, 'json-data/liveTabPosts.json', True)

def get_artists(community_id):
    req = f'/artistpedia/v1.0/community-{community_id}/highlight'
    print(write_single(req, 'json-data/artists.json', skip_exists=True))

# 'https://global.apis.naver.com/weverse/wevweb/post/v1.0/member-67b4c6fb2220ac6705aa97046f3503a1/posts?after=1699369636979%2C27138103&appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=postV1&filterType=MOMENT_VIEWER&language=en&limit=1&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178210447&wmd=Y1OTRioyq7vF2%2FSYTL09CAraDDM%3D'
# 'https://global.apis.naver.com/weverse/wevweb/member/v1.1/community-36/artistMembers?appId=be4d79eb8fc7bd008ee82c8ec4ff6fd4&fieldSet=artistMembersV1&filterType=MOMENT&language=en&os=WEB&platform=WEB&wpf=pc&wmsgpad=1735178123317&wmd=KHioIqTMvGRFPAxb3jUuMb0WdaE%3D'

if __name__ == '__main__':
    # print(debug_api("/post/v1.0/community-36/liveTabPosts?after=1729773708000,35506"))
    # print(debug_api("/post/v1.0/community-36/liveTabPosts?after=1729773708000,35506"))


    COMMUNITY_ID = 36
    # get_artists(COMMUNITY_ID)
    # write_all_posts(COMMUNITY_ID)
    # write_live_tab_posts(COMMUNITY_ID)

    # write_all_live_posts()

    write_all_live_comments()

# write_all_comments()