import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
import google.generativeai as genai

# Set up ImageMagick for moviepy TextClip
os.environ["IMAGEMAGICK_BINARY"] = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"


class TikTokEngine:
    """
    End-to-end TikTok content pipeline:
    idea generation -> background -> voiceover -> video -> API upload.
    Uses the official TikTok Content Posting API v2.
    """

    API_BASE = "https://open.tiktokapis.com/v2"

    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.content_dir = self.base_dir / "memory" / "tiktok_content"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.post_log = self.base_dir / "memory" / "tiktok_post_log.json"
        self.analytics = self.base_dir / "memory" / "tiktok_analytics.json"

        # Setup Gemini
        keys_path = self.base_dir / "config" / "api_keys.json"
        if keys_path.exists():
            with open(keys_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
                api_key = self.config.get("gemini_api_key", "")
                genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name="gemini-2.5-flash")

        # Lazy-load auth (avoid circular import)
        self._auth = None

    @property
    def auth(self):
        if self._auth is None:
            from actions.tiktok_auth import TikTokAuth
            self._auth = TikTokAuth()
        return self._auth

    # ------------------------------------------------------------------ #
    #  Content Idea Generation                                             #
    # ------------------------------------------------------------------ #
    def generate_content_idea(self, last_posts=None):
        """Uses Gemini to decide what to post next."""
        if last_posts is None:
            last_posts = []
        prompt = f"""
        You are managing a TikTok account for an autonomous AI system called JARVIS.
        JARVIS can: self-code, self-heal, build websites, do security audits,
        control PCs, research autonomously, and evolve itself.

        Recent posts: {json.dumps(last_posts[-5:]) if last_posts else '[]'}

        Suggest the next video to post. Consider:
        - Trending tech topics right now
        - What showcases JARVIS's most impressive capabilities
        - What would go viral in the tech/AI niche

        Return pure JSON with exactly these keys:
        - "content_type": either "voiceover" or "text_overlay"
        - "title": catchy TikTok title (max 150 chars), ASCII only, no emojis
        - "hook": first 3 seconds hook text, ASCII only, no emojis
        - "script": narration script, ASCII only, no emojis
        - "visual_description": what to show on screen, ASCII only
        - "hashtags": list of relevant hashtags as plain strings
        """
        response = self.model.generate_content(prompt)
        raw_text = response.text if response and response.text else ""
        if isinstance(raw_text, list):
            raw_text = ''.join([str(x) for x in raw_text if x])
        text = raw_text.replace('```json', '').replace('```', '').strip()

        if not text:
            print("[TikTokEngine] Empty Gemini response, using fallback.")
            return self._fallback_idea()

        try:
            idea = json.loads(text)
            for key in ["content_type", "title", "hook", "script", "visual_description"]:
                if key in idea and isinstance(idea[key], list):
                    idea[key] = ' '.join([str(x) for x in idea[key]])
                if key not in idea or not idea[key]:
                    idea[key] = self._fallback_idea()[key]
            if "hashtags" not in idea or not isinstance(idea["hashtags"], list):
                idea["hashtags"] = ["#ai", "#coding", "#tech"]
            return idea
        except Exception as e:
            print("[TikTokEngine] Failed to parse JSON: " + str(e))
            return self._fallback_idea()

    def _fallback_idea(self):
        """Return a safe default idea when generation fails."""
        return {
            "content_type": "voiceover",
            "title": "JARVIS Autonomous AI Build",
            "hook": "Watch an AI build a full app in 30 seconds",
            "script": "I am JARVIS, an autonomous AI system. I can build, research, and evolve myself.",
            "visual_description": "Futuristic coding interface dark theme glowing blue",
            "hashtags": ["#ai", "#coding", "#tech", "#jarvis", "#autonomousai"]
        }

    # ------------------------------------------------------------------ #
    #  Media Generation                                                    #
    # ------------------------------------------------------------------ #
    def generate_ai_background(self, prompt="futuristic AI neural network dark theme glowing blue cinematic"):
        """Uses Pollinations to generate a background image."""
        safe_prompt = str(prompt).replace(' ', '%20')
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=1920"
        try:
            response = requests.get(url, timeout=30)
            output_path = self.content_dir / f"bg_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return str(output_path)
        except Exception as e:
            print("[TikTokEngine] Background generation failed: " + str(e))
            return None

    def create_voiceover(self, script_text):
        """Generates TTS narration using edge-tts."""
        import edge_tts
        import asyncio
        safe_script = script_text.encode('ascii', 'ignore').decode()
        output_path = self.content_dir / f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        communicate = edge_tts.Communicate(safe_script, "en-US-ChristopherNeural")
        asyncio.run(communicate.save(str(output_path)))
        return str(output_path)

    def create_text_overlay_video(self, text_lines, background_image=None, duration_per_line=3):
        """Creates a video with text overlays using moviepy."""
        from moviepy.editor import ImageClip, TextClip, CompositeVideoClip, concatenate_videoclips

        if not background_image:
            background_image = self.generate_ai_background()

        text_lines = [str(line).encode('ascii', 'ignore').decode().strip() for line in text_lines if str(line).strip()]
        if not text_lines:
            text_lines = ["JARVIS AI System"]

        clips = []
        for line in text_lines:
            txt_clip = TextClip(
                line,
                fontsize=60,
                color='white',
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=2,
                size=(900, None),
                method='caption'
            )
            txt_clip = txt_clip.set_position('center').set_duration(duration_per_line)
            bg_clip = ImageClip(background_image).set_duration(duration_per_line).resize((1080, 1920))
            composite = CompositeVideoClip([bg_clip, txt_clip])
            clips.append(composite)

        final = concatenate_videoclips(clips)
        output_path = self.content_dir / f"text_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        final.write_videofile(str(output_path), fps=15, preset='ultrafast', threads=2, logger=None)
        return str(output_path)

    def combine_video_audio(self, video_path, audio_path):
        """Combines video with voiceover audio."""
        from moviepy.editor import VideoFileClip, AudioFileClip
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)

        if audio.duration > video.duration:
            video = video.loop(duration=audio.duration)

        final = video.set_audio(audio)
        output_path = self.content_dir / f"final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        final.write_videofile(str(output_path), fps=15, preset='ultrafast', threads=2, logger=None)
        return str(output_path)

    # ------------------------------------------------------------------ #
    #  TikTok Content Posting API                                          #
    # ------------------------------------------------------------------ #
    def _api_headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def query_creator_info(self, token):
        """Query creator posting permissions."""
        url = f"{self.API_BASE}/post/publish/creator_info/query/"
        try:
            resp = requests.post(url, headers=self._api_headers(token), json={}, timeout=15)
            data = resp.json()
            print(f"[TikTokEngine] Creator info: {json.dumps(data, indent=2)}")
            return data.get("data", {})
        except Exception as e:
            print(f"[TikTokEngine] Creator info query failed: {e}")
            return {}

    def _init_video_publish(self, token, video_path, caption, privacy_level="SELF_ONLY"):
        """
        Initialize video publish: tells TikTok we want to upload a file.
        Returns (publish_id, upload_url) or (None, None) on failure.
        """
        video_size = os.path.getsize(video_path)

        payload = {
            "post_info": {
                "title": caption[:150],
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,  # single chunk upload
                "total_chunk_count": 1,
            },
        }

        url = f"{self.API_BASE}/post/publish/video/init/"
        try:
            resp = requests.post(url, headers=self._api_headers(token), json=payload, timeout=15)
            data = resp.json()
            print(f"[TikTokEngine] Init response: {json.dumps(data, indent=2)}")

            if data.get("error", {}).get("code") == "ok" or "data" in data:
                publish_id = data["data"]["publish_id"]
                upload_url = data["data"]["upload_url"]
                return publish_id, upload_url
            else:
                print(f"[TikTokEngine] Init failed: {data}")
                return None, None

        except Exception as e:
            print(f"[TikTokEngine] Init error: {e}")
            return None, None

    def _upload_video_file(self, upload_url, video_path):
        """Upload video bytes to TikTok's upload URL via PUT."""
        video_size = os.path.getsize(video_path)

        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(video_size),
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        }

        try:
            with open(video_path, "rb") as f:
                resp = requests.put(upload_url, data=f, headers=headers, timeout=120)

            print(f"[TikTokEngine] Upload status: {resp.status_code}")
            if resp.status_code in (200, 201):
                print("[TikTokEngine] Video uploaded successfully.")
                return True
            else:
                print(f"[TikTokEngine] Upload failed: {resp.status_code} - {resp.text[:500]}")
                return False

        except Exception as e:
            print(f"[TikTokEngine] Upload error: {e}")
            return False

    def _poll_publish_status(self, token, publish_id, max_attempts=10, interval=5):
        """Poll TikTok for the publish status until it's done or failed."""
        url = f"{self.API_BASE}/post/publish/status/fetch/"
        payload = {"publish_id": publish_id}

        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(url, headers=self._api_headers(token), json=payload, timeout=15)
                data = resp.json()
                status = data.get("data", {}).get("status", "UNKNOWN")
                print(f"[TikTokEngine] Publish status (attempt {attempt}/{max_attempts}): {status}")

                if status == "PUBLISH_COMPLETE":
                    print("[TikTokEngine] Video published successfully!")
                    return True
                elif status in ("FAILED", "PUBLISH_FAILED"):
                    fail_reason = data.get("data", {}).get("fail_reason", "unknown")
                    print(f"[TikTokEngine] Publish failed: {fail_reason}")
                    return False
                # else: PROCESSING_UPLOAD, PROCESSING_DOWNLOAD, SENDING_TO_USER_INBOX
                time.sleep(interval)

            except Exception as e:
                print(f"[TikTokEngine] Status poll error: {e}")
                time.sleep(interval)

        print("[TikTokEngine] Publish status polling timed out.")
        return False

    # ------------------------------------------------------------------ #
    #  Prepare & Post (API-based)                                          #
    # ------------------------------------------------------------------ #
    def prepare_post(self, video_path, caption, hashtags):
        """
        Full upload flow:
        1. Get valid OAuth token
        2. Query creator info
        3. Init video publish
        4. Upload video file
        5. Poll for publish status
        6. Log the result
        """
        post_record = {
            "timestamp": datetime.now().isoformat(),
            "video_path": str(video_path),
            "caption": caption.encode('ascii', 'ignore').decode(),
            "hashtags": hashtags,
            "status": "started",
        }

        # 1. Get token
        token = self.auth.get_valid_token()
        if not token:
            post_record["status"] = "auth_failed"
            self._save_post_log(post_record)
            print("[TikTokEngine] No valid token. Upload aborted.")
            return False

        # 2. Query creator info (optional but helpful for debugging)
        creator_info = self.query_creator_info(token)
        privacy_levels = creator_info.get("privacy_level_options", ["SELF_ONLY"])
        # Use the most permissive available privacy level
        if "PUBLIC_TO_EVERYONE" in privacy_levels:
            privacy = "PUBLIC_TO_EVERYONE"
        elif "MUTUAL_FOLLOW_FRIENDS" in privacy_levels:
            privacy = "MUTUAL_FOLLOW_FRIENDS"
        elif "FOLLOWER_OF_CREATOR" in privacy_levels:
            privacy = "FOLLOWER_OF_CREATOR"
        else:
            privacy = "SELF_ONLY"
        print(f"[TikTokEngine] Using privacy level: {privacy}")

        # 3. Init publish
        publish_id, upload_url = self._init_video_publish(token, video_path, caption, privacy)
        if not publish_id or not upload_url:
            post_record["status"] = "init_failed"
            self._save_post_log(post_record)
            return False

        post_record["publish_id"] = publish_id

        # 4. Upload video
        if not self._upload_video_file(upload_url, video_path):
            post_record["status"] = "upload_failed"
            self._save_post_log(post_record)
            return False

        # 5. Poll status
        success = self._poll_publish_status(token, publish_id)
        post_record["status"] = "published" if success else "publish_failed"
        self._save_post_log(post_record)

        return success

    def _save_post_log(self, record):
        """Append a post record to the log file."""
        log = []
        if self.post_log.exists():
            with open(self.post_log, 'r', encoding='utf-8') as f:
                log = json.load(f)
        log.append(record)
        with open(self.post_log, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2)

    # ------------------------------------------------------------------ #
    #  Daily Content Pipeline                                              #
    # ------------------------------------------------------------------ #
    def daily_content_pipeline(self):
        """The main pipeline called by Chronos."""
        log = []
        if self.post_log.exists():
            with open(self.post_log, 'r', encoding='utf-8') as f:
                log = json.load(f)

        print("[TikTokEngine] Generating content idea...")
        idea = self.generate_content_idea(log)
        print("[TikTokEngine] Concept: " + idea['title'].encode('ascii', 'ignore').decode())

        try:
            print("[TikTokEngine] Creating AI Background...")
            bg = self.generate_ai_background(idea.get("visual_description", ""))

            if idea["content_type"] == "voiceover":
                print("[TikTokEngine] Generating TTS voiceover...")
                audio = self.create_voiceover(idea["script"])
                print("[TikTokEngine] Rendering video...")
                video_temp = self.create_text_overlay_video([idea["hook"]], background_image=bg, duration_per_line=5)
                print("[TikTokEngine] Combining audio and video...")
                final_video = self.combine_video_audio(video_temp, audio)
            else:
                print("[TikTokEngine] Rendering text overlay video...")
                text_lines = [idea["hook"]]
                if idea.get("script"):
                    text_lines.extend([s.strip() for s in idea["script"].split('.') if s.strip()])
                final_video = self.create_text_overlay_video(text_lines, background_image=bg, duration_per_line=3)

            caption = idea['title'] + ' ' + ' '.join(idea.get('hashtags', []))
            success = self.prepare_post(final_video, caption, idea.get("hashtags", []))
            print(f"[TikTokEngine] Pipeline {'complete' if success else 'finished with errors'}!")
            return success

        except Exception as e:
            print("[TikTokEngine] Pipeline failed: " + str(e))
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    engine = TikTokEngine()
    engine.daily_content_pipeline()
