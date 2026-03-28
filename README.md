# Weverse Archiver

**This is for learning / reference. I recommend checking out: https://github.com/woogie0923/archiverse**

A simple tool to archive posts, media, and metadata from Weverse communities.

Currently it mainly archives json data. Limitations on downloading videos in posts.

### Features
* **Archive Metadata:** Saves JSON data for the Media tab, Live tab, and Artist tab.
* **Artist Posts:** Archives all posts made by artists and official channels.
* **Moments:** Downloads artist Moments.
* **Lives:** Downloads all lives that you have access to.
* **Profile Pictures:** Downloads artist profile pictures.
* **Post Media:** Downloads images attached to artist posts.
* **Comments:** Fetches and saves comments for posts and live streams.

### Not Working
* Weverse DM

### Requirements
* Python 3.x
  * Install requirements `pip install -r requirements.txt` 
* A browser logged into Weverse
* Need to edit python files for config
* [yt-dlp](https://github.com/yt-dlp/yt-dlp), [mp4decrypt](https://www.bento4.com/) and [ffmpeg](https://www.ffmpeg.org/) installed in your path

### Usage
* Edit `main.py`
  * In `download_community`, set your community name https://weverse.io/fromis9/ 
  * Edit `ydl_params` for your browser (default to firefox)
* Run main.py `python main.py`
