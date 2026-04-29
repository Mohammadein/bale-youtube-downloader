import os
import time
import requests
import subprocess
import yt_dlp
import shutil

# ================== تنظیمات ==================

TOKEN = os.environ["token"]
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"

DOWNLOAD_DIR = "downloads"
PART_SIZE = "19m"   # توجه: RAR از m یا k استفاده می‌کند، نه M

# ============================================

AVAILABLE_HEIGHTS = [144, 240, 360, 480, 720, 1080, 1440, 2160]
pending_links = {}

# ---------- توابع ارسال ----------

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
        r = requests.post(url, data=data, files=files, timeout=600)
        print("sendDocument:", r.text)


# ---------- دانلود یوتیوب ----------

def download_youtube_video(url: str, height: int) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
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

def process_video(chat_id, url, height):
    try:
        send_message(chat_id, f"⬇️ Downloading video in {height}p quality...")

        video_path = download_youtube_video(url, height)
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)

        base_name, _ = os.path.splitext(video_name)

        send_message(chat_id, "🗜 Creating multipart RAR...")

        rar_base = os.path.join(video_dir, base_name + ".rar")

        # ایجاد فایل rar چند بخشی
        subprocess.run(
            [
                "rar", "a",
                f"-v{PART_SIZE}",   # مثال: -v19m
                "-ep",
                rar_base,
                video_path
            ],
            check=True
        )

        # فایل‌های خروجی:
        # video.part1.rar
        # video.part2.rar
        # ...

        parts = sorted([
            os.path.join(video_dir, f)
            for f in os.listdir(video_dir)
            if f.startswith(base_name + ".part") and f.endswith(".rar")
        ])

        total = len(parts)

        for i, part in enumerate(parts, 1):
            send_message(chat_id, f"📤 Sending part {i}/{total}")
            send_document(chat_id, part)

        send_message(chat_id, "✅ Upload completed")

    except Exception as e:
        send_message(chat_id, f"❌ Error: {e}")

    finally:
        cleanup(video_path)


# ---------- پاکسازی ----------

def cleanup(video_path):
    try:
        dir_path = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)
        base_name, _ = os.path.splitext(video_name)

        for f in os.listdir(dir_path):
            full = os.path.join(dir_path, f)

            # حذف mp4
            if f == video_name:
                os.remove(full)
                continue

            # حذف rar های چندبخشی
            if f.startswith(base_name + ".part") and f.endswith(".rar"):
                os.remove(full)

    except Exception as e:
        print("Cleanup error:", e)


# ---------- دریافت پیام‌ها ----------

def get_updates(offset=None):
    return requests.get(
        BASE_URL + "getUpdates",
        params={"timeout": 30, "offset": offset},
        timeout=35
    ).json()


def show_quality_list(chat_id):
    txt = "📺 لطفاً کیفیت مورد نظرت را انتخاب کن:\n"
    txt += "\n".join([f"{i+1}) {h}p" for i, h in enumerate(AVAILABLE_HEIGHTS)])
    send_message(chat_id, txt)
    send_message(chat_id, "🔢 عدد مربوط به کیفیت را بفرست (مثلاً 5 برای 720p)")


# ---------- حلقه اصلی ----------

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

                # انتخاب کیفیت
                if chat_id in pending_links:
                    try:
                        choice = int(text)
                        if 1 <= choice <= len(AVAILABLE_HEIGHTS):
                            height = AVAILABLE_HEIGHTS[choice - 1]
                            url = pending_links.pop(chat_id)
                            process_video(chat_id, url, height)
                        else:
                            send_message(chat_id, "❌ عدد نامعتبر است.")
                            show_quality_list(chat_id)
                    except ValueError:
                        send_message(chat_id, "🔢 فقط عدد بفرست.")
                        show_quality_list(chat_id)
                    continue

                # دریافت لینک
                if text.startswith("http"):
                    pending_links[chat_id] = text
                    show_quality_list(chat_id)
                else:
                    send_message(chat_id, "🔗 لطفاً لینک یوتیوب ارسال کن")

        except Exception as e:
            print("Main loop error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
