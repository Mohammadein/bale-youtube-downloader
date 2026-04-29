import os
import time
import requests
import subprocess
import yt_dlp
import shutil

# ================== تنظیمات ==================

TOKEN = os.getenv("token")   # تغییر شماره 1
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"

DOWNLOAD_DIR = "downloads"
PART_SIZE = "19M"

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
def get_available_formats(url):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", [])
    qualities = []

    for f in formats:
        if f.get("vcodec") != "none" and f.get("height") and f["height"] >= 144:
            qualities.append(f"{f['height']}p")

    # حذف تکراری‌ها و مرتب‌سازی عددی
    qualities = sorted(set(qualities), key=lambda x: int(x.replace("p", "")))

    return qualities



# ---------- دانلود یوتیوب ----------
def download_youtube_video(url: str, quality: str) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # تغییر شماره 3 (فرمت بر اساس کیفیت انتخاب‌شده)
    ydl_opts = {
        "format": f"bestvideo[height<={quality.replace('p','')}]+bestaudio/best[height<={quality.replace('p','')}]",
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
user_quality_choice = {}   # ذخیره کیفیت انتخابی کاربران


def process_video(chat_id, url):
    try:
        # اگر کیفیت انتخاب نشده → ابتدا کیفیت‌ها را بفرستیم
        if chat_id not in user_quality_choice:
            qualities = get_available_formats(url)
            qtext = "لطفاً یکی از کیفیت‌های موجود را بفرست:\n" + "\n".join(qualities)
            user_quality_choice[chat_id] = {"url": url, "waiting": True, "qualities": qualities}
            send_message(chat_id, qtext)
            return

        # کیفیت انتخاب شده:
        quality = user_quality_choice[chat_id]["choice"]

        send_message(chat_id, f"⬇️ Downloading video in {quality} ...")

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

        # تغییر شماره 2: zip شدن پارت‌ها
        zipped_parts = []
        for part in parts:
            zip_path = part + ".zip"
            shutil.make_archive(part, "zip", root_dir=video_dir, base_dir=os.path.basename(part))
            zipped_parts.append(zip_path)

        total = len(zipped_parts)

        for i, part in enumerate(zipped_parts, 1):
            send_message(chat_id, f"📤 Sending part {i}/{total}")
            send_document(chat_id, part)

        send_message(chat_id, "✅ Upload completed")

    except Exception as e:
        send_message(chat_id, f"❌ Error: {e}")

    finally:
        user_quality_choice.pop(chat_id, None)
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

                # اگر در حال انتخاب کیفیت است:
                if chat_id in user_quality_choice and user_quality_choice[chat_id]["waiting"]:
                    if text in user_quality_choice[chat_id]["qualities"]:
                        user_quality_choice[chat_id]["choice"] = text
                        user_quality_choice[chat_id]["waiting"] = False
                        process_video(chat_id, user_quality_choice[chat_id]["url"])
                    else:
                        send_message(chat_id, "❗ کیفیت نامعتبر است.")
                    continue

                if text.startswith("http"):
                    process_video(chat_id, text)
                else:
                    send_message(chat_id, "🔗 لطفاً لینک یوتیوب ارسال کن")

        except Exception as e:
            print("Main loop error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
