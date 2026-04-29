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

# دیکشنری برای ذخیره وضعیت کاربران (لینک و کیفیت‌های پیدا شده)
user_sessions = {}

# ============================================

def send_message(chat_id, text):
    requests.post(
        BASE_URL + "sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30
    )

def send_document(chat_id, file_path):
    url = BASE_URL + "sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        requests.post(url, data={"chat_id": chat_id}, files=files, timeout=300)

def get_video_qualities(url):
    """استخراج لیست کیفیت‌های موجود"""
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        heights = set()
        for f in formats:
            if f.get('vcodec') != 'none' and f.get('height'):
                heights.add(f['height'])
        
        return sorted(list(heights))

def download_youtube_video(url, target_height):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # انتخاب بهترین ویدیو با کیفیت انتخابی + بهترین صدا و تبدیل به mp4
    ydl_opts = {
        "format": f"bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    # اطمینان از اینکه پسوند نهایی mp4 است (به دلیل merge)
    base, _ = os.path.splitext(filename)
    final_path = base + ".mp4"
    return final_path if os.path.exists(final_path) else filename

def process_video(chat_id, url, quality):
    try:
        send_message(chat_id, f"⬇️ Downloading in {quality}p...")
        video_path = download_youtube_video(url, quality)
        
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)

        send_message(chat_id, "✂️ Splitting video...")
        prefix = os.path.join(video_dir, video_name + ".part_")

        subprocess.run(["split", "-b", PART_SIZE, video_path, prefix], check=True)

        parts = sorted([
            os.path.join(video_dir, f)
            for f in os.listdir(video_dir)
            if f.startswith(video_name + ".part_")
        ])

        for i, part in enumerate(parts, 1):
            send_message(chat_id, f"📤 Sending part {i}/{len(parts)}")
            send_document(chat_id, part)

        send_message(chat_id, "✅ Done!")
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
    except:
        pass

def get_updates(offset=None):
    try:
        r = requests.get(BASE_URL + "getUpdates", params={"timeout": 30, "offset": offset}, timeout=35)
        return r.json()
    except:
        return {}

def main():
    offset = None
    print("✅ Bot is running...")

    while True:
        updates = get_updates(offset)
        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message")
            if not msg or "text" not in msg: continue

            chat_id = msg["chat"]["id"]
            text = msg["text"].strip()

            # اگر کاربر قبلاً لینک فرستاده و الان دارد عدد کیفیت را انتخاب می‌کند
            if chat_id in user_sessions and text.isdigit():
                idx = int(text) - 1
                session = user_sessions[chat_id]
                if 0 <= idx < len(session['qualities']):
                    selected_q = session['qualities'][idx]
                    video_url = session['url']
                    del user_sessions[chat_id] # پاک کردن جلسه
                    process_video(chat_id, video_url, selected_q)
                else:
                    send_message(chat_id, "عدد انتخاب شده معتبر نیست.")
                continue

            # دریافت لینک جدید
            if text.startswith("http"):
                send_message(chat_id, "🔎 Checking qualities...")
                try:
                    qs = get_video_qualities(text)
                    if not qs:
                        send_message(chat_id, "هیچ کیفیتی برای این ویدیو یافت نشد.")
                        continue
                    
                    user_sessions[chat_id] = {'url': text, 'qualities': qs}
                    
                    menu = "یک کیفیت را انتخاب کنید (فقط عدد را بفرستید):\n\n"
                    for i, q in enumerate(qs, 1):
                        menu += f"{i} - {q}p\n"
                    send_message(chat_id, menu)
                except Exception as e:
                    send_message(chat_id, f"خطا در بررسی لینک: {e}")
            else:
                send_message(chat_id, "🔗 لطفاً یک لینک یوتیوب معتبر بفرستید.")

        time.sleep(1)

if __name__ == "__main__":
    main()
