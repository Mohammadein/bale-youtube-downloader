import os
import time
import requests
import subprocess
import yt_dlp

TOKEN = "665419412:REnWbsHEGIC_EP0kjB_VbKhxzTpLyZsFPG4"
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"

DOWNLOAD_DIR = "downloads"
PART_SIZE = "19M"

user_sessions = {}


def send_message(chat_id, text):
    requests.post(
        BASE_URL + "sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30
    )


def send_document(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(
            BASE_URL + "sendDocument",
            data={"chat_id": chat_id},
            files={"document": (os.path.basename(file_path), f)},
            timeout=300
        )


def get_video_formats(url):

    ydl_opts = {"quiet": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []

    for f in info["formats"]:
        if f.get("vcodec") != "none" and f.get("height"):
            formats.append({
                "id": f["format_id"],
                "height": f["height"],
                "ext": f["ext"]
            })

    # حذف کیفیت‌های تکراری
    seen = set()
    clean = []

    for f in sorted(formats, key=lambda x: x["height"]):
        if f["height"] not in seen:
            clean.append(f)
            seen.add(f["height"])

    return clean


def download_video(url, format_id):

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": format_id,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "quiet": True,
        "merge_output_format": "mp4"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    base, _ = os.path.splitext(filename)
    path = base + ".mp4"

    if not os.path.exists(path):
        path = filename

    return path


def split_and_send(chat_id, video_path):

    video_dir = os.path.dirname(video_path)
    video_name = os.path.basename(video_path)

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
        send_message(chat_id, f"Sending part {i}/{total}")
        send_document(chat_id, part)

    send_message(chat_id, "✅ Upload completed")

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
    return requests.get(
        BASE_URL + "getUpdates",
        params={"timeout": 30, "offset": offset},
        timeout=35
    ).json()


def handle_message(chat_id, text):

    if chat_id in user_sessions and text.isdigit():

        session = user_sessions[chat_id]
        idx = int(text) - 1

        if 0 <= idx < len(session["formats"]):

            format_id = session["formats"][idx]["id"]
            url = session["url"]

            send_message(chat_id, "⬇️ Downloading video...")

            video_path = download_video(url, format_id)

            send_message(chat_id, "✂️ Splitting video...")

            split_and_send(chat_id, video_path)

            del user_sessions[chat_id]

            return

        else:
            send_message(chat_id, "عدد معتبر نیست")
            return

    if text.startswith("http"):

        send_message(chat_id, "🔎 Getting available qualities...")

        formats = get_video_formats(text)

        if not formats:
            send_message(chat_id, "❌ کیفیتی پیدا نشد")
            return

        user_sessions[chat_id] = {
            "url": text,
            "formats": formats
        }

        msg = "کیفیت مورد نظر را انتخاب کن:\n\n"

        for i, f in enumerate(formats, 1):
            msg += f"{i} - {f['height']}p\n"

        send_message(chat_id, msg)

    else:
        send_message(chat_id, "🔗 لطفاً لینک یوتیوب بفرست")


def main():

    offset = None

    print("Bot started")

    while True:

        updates = get_updates(offset)

        for update in updates.get("result", []):

            offset = update["update_id"] + 1

            msg = update.get("message")

            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            text = msg.get("text", "").strip()

            handle_message(chat_id, text)

        time.sleep(1)


if __name__ == "__main__":
    main()
