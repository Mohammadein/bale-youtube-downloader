import os
import time
import requests
import subprocess
import json

TOKEN = "665419412:REnWbsHEGIC_EP0kjB_VbKhxzTpLyZsFPG4"
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"

ALLOWED_USERS_FILE = "allowed_users.txt"
DOWNLOAD_DIR = "downloads"
PART_SIZE = "19M"

# وضعیت کاربر در حال حاضر: "main" یا "awaiting_youtube" یا "awaiting_direct"
user_states = {}

def load_allowed_users():
    if not os.path.exists(ALLOWED_USERS_FILE):
        return set()
    with open(ALLOWED_USERS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def is_user_allowed(user_id):
    allowed = load_allowed_users()
    return str(user_id) in allowed

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(BASE_URL + "sendMessage", json=payload, timeout=30)
    print("sendMessage:", r.text)

def get_updates(offset=None):
    return requests.get(
        BASE_URL + "getUpdates",
        params={"timeout": 30, "offset": offset},
        timeout=35
    ).json()

def download_youtube_video(url):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
    }
    import yt_dlp
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    base, _ = os.path.splitext(filename)
    video_path = base + ".mp4"
    if not os.path.exists(video_path):
        video_path = filename
    return video_path

def download_file(url):
    filename = url.split("/")[-1]
    if not filename:
        filename = "downloaded_file"
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    subprocess.run(["wget", "-O", filepath, url], check=True)
    return filepath

def process_video(chat_id, url, only_parts=None):
    try:
        send_message(chat_id, "⬇️ در حال دانلود ویدیو...")
        video_path = download_youtube_video(url) if "youtube.com" in url else download_file(url)
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)
        send_message(chat_id, "✂️ در حال برش فایل/ویدیو...")
        prefix = os.path.join(video_dir, video_name + ".part_")
        subprocess.run(["split", "-b", PART_SIZE, video_path, prefix], check=True)
        parts = sorted([os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.startswith(video_name + ".part_")])
        total = len(parts)
        for i, part in enumerate(parts, 1):
            if only_parts and i not in only_parts:
                continue
            send_message(chat_id, f"📤 ارسال قسمت {i}/{total}")
            send_document(chat_id, part)
        send_message(chat_id, "✅ فرایند با موفقیت انجام شد.")
    except Exception as e:
        send_message(chat_id, f"❌ خطا: {e}")
    finally:
        cleanup(video_path)

def send_document(chat_id, file_path):
    url = BASE_URL + "sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
        requests.post(url, data={"chat_id": chat_id}, files=files, timeout=300)

def cleanup(file_path):
    try:
        os.remove(file_path)
    except:
        pass

def handle_main_menu(chat_id):
    reply_markup = {
        "keyboard": [
            [{"text": "YouTube"}],
            [{"text": "Direct Link"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }
    send_message(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)
    user_states[chat_id] = "main"

def handle_back(chat_id):
    handle_main_menu(chat_id)

def process_message(update):
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    if not is_user_allowed(user_id):
        send_message(chat_id, "شما مجاز به استفاده از این ربات نیستید.")
        return

    # وضعیت کاربر
    state = user_states.get(chat_id, "main")

    if text == "/start" or text == "بازگشت":
        handle_main_menu(chat_id)
        return

    if state == "main":
        # منو اصلی
        if text == "YouTube":
            send_message(chat_id, "لطفاً لینک یوتیوب را ارسال کنید یا با نوشتن 'بازگشت' به منو برگردید.")
            user_states[chat_id] = "awaiting_youtube"
        elif text == "Direct Link":
            send_message(chat_id, "لطفاً لینک مستقیم را ارسال کنید یا با نوشتن 'بازگشت' به منو برگردید.")
            user_states[chat_id] = "awaiting_direct"
        else:
            handle_main_menu(chat_id)
    elif state == "awaiting_youtube":
        if text.startswith("http"):
            process_video(chat_id, text)
        else:
            send_message(chat_id, "لطفاً لینک معتبر ارسال کنید.")
        user_states[chat_id] = "main"
    elif state == "awaiting_direct":
        if text.startswith("http"):
            process_video(chat_id, text)
        else:
            send_message(chat_id, "لطفاً لینک معتبر ارسال کنید.")
        user_states[chat_id] = "main"

def main():
    offset = None
    print("ربات شروع به کار کرد...")
    while True:
        try:
            updates = get_updates(offset)
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                handle_message(update)
        except Exception as e:
            print("اشکال در حلقه اصلی:", e)
            time.sleep(3)

def handle_message(update):
    process_message(update)

if __name__ == "__main__":
    handle_main_menu(0)  # شروع با منو
    main()
