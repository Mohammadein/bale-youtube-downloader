import os
import time
import requests
import subprocess
import yt_dlp
import shutil

# ================== تنظیمات ==================

TOKEN = os.getenv("token") 
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"

DOWNLOAD_DIR = "downloads"
PART_SIZE = "19M"

# ============================================

pending_links = {}  # برای نگهداری لینک‌ها که منتظر انتخاب کیفیت هستند


def send_message(chat_id, text):
    r = requests.post(
        BASE_URL + "sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30
    )
    print("sendMessage:", r.text)


def send_document(chat_id, file_path):
    url = BASE_URL + "sendDocument"
    with open(file_path, "rb") as f:
        files = {
            "document": (
                os.path.basename(file_path),
                f,
                "application/octet-stream"
            )
        }
        data = {"chat_id": chat_id}
        r = requests.post(url, data=data, files=files, timeout=300)
        print("sendDocument:", r.text)


# ---------- دانلود یوتیوب ----------

def download_youtube_video(url: str, quality: int) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        # تنظیم کیفیت بر اساس انتخاب کاربر
        "format": f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    base, _ = os.path.splitext(filename)
    video_path = base + ".mp4"

    # اگر فایل نهایی mp4 یافت نشد، همان نام فایل اولیه
    if not os.path.exists(video_path):
        video_path = filename

    return video_path


# ---------- پردازش و ارسال ----------

def process_video(chat_id, url, quality):
    try:
        send_message(chat_id, f"⬇️ در حال دانلود ویدیو با کیفیت {quality}p ...")

        video_path = download_youtube_video(url, quality)
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)

        send_message(chat_id, "✂️ در حال تقسیم ویدیو به بخش‌های کوچک‌تر...")

        prefix = os.path.join(video_dir, video_name + ".part_")

        subprocess.run(
            ["split", "-b", PART_SIZE, video_path, prefix],
            check=True
        )

        parts = sorted([
            os.path.join(video_dir, f)
            for f in os.listdir(video_dir)
            if f.startswith(video_name + ".part_")
        ])

        total = len(parts)

        for i, part in enumerate(parts, 1):
            send_message(chat_id, f"📤 در حال ارسال بخش {i}/{total}")
            send_document(chat_id, part)

        send_message(chat_id, "✅ ارسال ویدیو تکمیل شد")

    except Exception as e:
        send_message(chat_id, f"❌ خطا در پردازش: {e}")

    finally:
        cleanup(video_path)


def cleanup(video_path):
    try:
        dir_path = os.path.dirname(video_path)
        base = os.path.basename(video_path)

        for f in os.listdir(dir_path):
            if f.startswith(base):
                os.remove(os.path.join(dir_path, f))
    except Exception as e:
        print("Cleanup error:", e)


# ---------- دریافت پیام‌ها ----------

def get_updates(offset=None):
    return requests.get(
        BASE_URL + "getUpdates",
        params={"timeout": 30, "offset": offset},
        timeout=35
    ).json()


def main():
    offset = None
    print("✅ Bale bot started...")

    qualities = [144, 240, 360, 480, 720, 1080, 1440, 2160]

    while True:
        try:
            updates = get_updates(offsetet
