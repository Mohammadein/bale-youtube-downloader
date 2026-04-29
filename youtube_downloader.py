import os
import yt_dlp


def download_youtube_video(url: str, download_dir: str = "downloads") -> str:
    """
    یک ویدیو از یوتیوب دانلود می‌کند و آدرس فایل را برمی‌گرداند.
    
    پارامترها:
        url: لینک ویدیوی یوتیوب (youtu.be یا youtube.com)
        download_dir: پوشه‌ای که ویدیوها داخلش ذخیره می‌شوند
    
    خروجی:
        مسیر کامل فایل ویدیو روی دیسک
    
    اگر دانلود موفق نباشد، Exception بالا می‌برد.
    """

    # 1) ساخت پوشه اگر وجود ندارد
    os.makedirs(download_dir, exist_ok=True)

    # 2) تنظیمات yt-dlp
    # %(id)s یا %(title)s را می‌توانی طبق نیاز عوض کنی
    ydl_opts = {
        "format": "mp4",  # یا 'bestvideo+bestaudio/best'
        "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,        # مطمئن شو فقط یک ویدیو دانلود می‌شود
        "quiet": True,             # لاگ‌های اضافه چاپ نشود
        "merge_output_format": "mp4",
    }

    # 3) دانلود
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # 4) ساخت مسیر فایل خروجی
    filename = ydl.prepare_filename(info)
    # چون merge_output_format را mp4 گذاشتیم، اگر فرمت چیز دیگری بود، تبدیل شده
    base, _ = os.path.splitext(filename)
    filepath = base + ".mp4"

    if not os.path.exists(filepath):
        # اگر تبدیل انجام نشده بود، همان filename را برگردان
        filepath = filename

    return filepath
