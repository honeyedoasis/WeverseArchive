# Weverse Archiver

A simple tool to archive posts, media, and metadata from Weverse communities.

Currently it mainly archives json data. Limitations on downloading videos in posts.

### Features
* **Archive Metadata:** Saves JSON data for the Media tab, Live tab, and Artist tab.
* **Artist Posts:** Archives all posts made by artists and official channels. **Can't download membership videos!**.
* **Moments:** Downloads artist Moments.
* **Profile Pictures:** Downloads artist profile pictures.
* **Post Media:** Downloads images attached to artist posts.
* **Comments:** Fetches and saves comments for posts and live streams.

### Not Working
* Membership Post Videos
* Weverse DM
* Membership Live

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
