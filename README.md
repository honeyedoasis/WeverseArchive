# Weverse Archiver

A simple tool to archive posts, media, and metadata from Weverse communities.

### Features (What it can do)
* **Archive Metadata:** Saves JSON data for the Media tab, Live tab, and Artist tab.
* **Artist Posts:** Archives all posts made by artists and official channels. **Can't download videos!**.
* **Moments:** Downloads artist Moments.
* **Profile Pictures:** Downloads artist profile pictures.
* **Post Media:** Downloads images attached to artist posts.
* **Comments:** Fetches and saves comments for posts and live streams.

### Not Working
* **Artist Post Videos:** Does not currently download videos attached to standard artist posts.
* **Direct Messages (DMs):** The DM archiving feature is non-functional.
* **Membership Content:** Skips downloading membership-only videos.
* **Live VODs:** Downloading full Live replays is disabled by default due to processing time.
* **Browser Support:** Currently hardcoded to only extract cookies from Firefox.

### Requirements
* Python 3.x
* A browser logged into Weverse
* Need to edit python files for config

### Usage
* Edit `main.py` config
  * Edit `COMMUNITY_NAME` for your community (https://weverse.io/fromis9/) 
  * Edit `ydl_params` for your browser (default to firefox) 
* Install requirements `pip install -r requirements.txt`
* Run main.py `python main.py`
