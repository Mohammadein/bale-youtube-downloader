import os
import time
import requests
import subprocess
import yt_dlp

# ================== تنظیمات ==================

TOKEN = "665419412:REnWbsHEGIC_EP0kjB_VbKhxzTpLyZsFPG4"
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"

DOWNLOAD_DIR = "downloads"
PART_SIZE = "19M"

# ذخیره وضعیت کاربران برای انتخاب کیفیت
user_sessions = {}

# ============================================


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


# ---------- دریافت کیفیت‌ها ----------

def get_video_qualities(url):
    STANDARD_QUALITIES = [144, 240, 360, 480, 720, 1080, 1440, 2160]

    ydl_opts = {
        'quiet': True,
        'skip_download': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])

        available = set()

        for f in formats:
            if f.get('vcodec') != 'none' and f.get('height'):
                available.add(f['height'])

        # فقط کیفیت‌های استاندارد که موجود هستند
        result = [q for q in STANDARD_QUALITIES if q in available]

        return result



# ---------- دانلود یوتیوب با کیفیت انتخابی ----------

def download_youtube_video(url: str, target_height: int) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": f"bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]/best",
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

    if not os.path.exists(video_path):
        video_path = filename

    return video_path


# ---------- پردازش و ارسال ----------

def process_video(chat_id, url, quality):
    try:
        send_message(chat_id, f"⬇️ Downloading in {quality}p...")

        video_path = download_youtube_video(url, quality)
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)

        send_message(chat_id, "✂️ Splitting video...")

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
            send_message(chat_id, f"📤 Sending part {i}/{total}")
            send_document(chat_id, part)

        send_message(chat_id, "✅ Upload completed")

    except Exception as e:
        send_message(chat_id, f"❌ Error: {e}")

    finally:
        if 'video_path' in locals():
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

    while True:
        try:
            updates = get_updates(offset)

            for update in updates.get("result", []):
                offset = update["update_id"] + 1

                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue

                chat_id = msg["chat"]["id"]
                text = msg["text"].strip()

                # اگر کاربر در حال انتخاب کیفیت است
                if chat_id in user_sessions and text.isdigit():
                    idx = int(text) - 1
                    session = user_sessions[chat_id]

                    if 0 <= idx < len(session["qualities"]):
                        selected_q = session["qualities"][idx]
                        video_url = session["url"]

                        del user_sessions[chat_id]

                        process_video(chat_id, video_url, selected_q)
                    else:
                        send_message(chat_id, "❌ عدد نامعتبر است.")
                    continue

                # اگر لینک جدید ارسال شده
                if text.startswith("http"):
                    send_message(chat_id, "🔎 Checking qualities...")

                    try:
                        qs = get_video_qualities(text)

                        if not qs:
                            send_message(chat_id, "❌ کیفیتی یافت نشد.")
                            continue

                        user_sessions[chat_id] = {
                            "url": text,
                            "qualities": qs
                        }

                        menu = "یک کیفیت را انتخاب کنید (فقط عدد را ارسال کنید):\n\n"

                        for i, q in enumerate(qs, 1):
                            menu += f"{i} - {q}p\n"

                        send_message(chat_id, menu)

                    except Exception as e:
                        send_message(chat_id, f"❌ خطا در بررسی لینک:\n{e}")

                else:
                    send_message(chat_id, "🔗 لطفاً لینک یوتیوب ارسال کن")

        except Exception as e:
            print("Main loop error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
