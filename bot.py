import os
import time
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# কনফিগারেশন (আপনার তথ্য এখানে দিন)
API_ID = "19234664"
API_HASH = "29c2f3b3d115cf1b0231d816deb271f5"
BOT_TOKEN = "8710959010:AAHfutLem56XMMvNN9GG6n-xwJUiKYA2J7s"

app = Client("video_merger", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ইউজার ডাটা রাখার জন্য ডিকশনারি
user_data = {}

# প্রোগ্রেস বার তৈরি করার ফাংশন
def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        
        progress = "[{0}{1}]".format(
            ''.join(["■" for i in range(int(percentage / 10))]),
            ''.join(["□" for i in range(10 - int(percentage / 10))])
        )
        
        tmp = f"{action}\n{progress} {round(percentage, 2)}%\n" \
              f"সাইজ: {current/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n"
        
        try:
            status_msg.edit_text(tmp)
        except:
            pass

@app.on_message(filters.command("start"))
async def start(client, message):
    user_data[message.chat.id] = []
    await message.reply_text(
        "স্বাগতম! আমি আপনার ছোট ভিডিওগুলো জোড়া লাগিয়ে একটি বড় ভিডিও বানিয়ে দেব।\n\n"
        "১. একে একে ভিডিও (এপিসোড) গুলো পাঠান।\n"
        "২. সব পাঠানো শেষ হলে 'Done' লিখুন।"
    )

@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = []

    status_msg = await message.reply_text("ডাউনলোড শুরু হচ্ছে...", quote=True)
    start_time = time.time()

    # ডাউনলোড করা
    file_path = await message.download(
        file_name=f"downloads/{chat_id}/{time.time()}.mp4",
        progress=progress_bar,
        progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
    )

    user_data[chat_id].append(file_path)
    episode_num = len(user_data[chat_id])
    await status_msg.edit_text(f"✅ এপিসোড {episode_num} যুক্ত হয়েছে।\nএখন পরের এপিসোড পাঠান অথবা 'Done' লিখে মেসেজ দিন।")

@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos(client, message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or len(user_data[chat_id]) < 2:
        await message.reply_text("কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("⚙️ ভিডিওগুলো জোড়া লাগানো হচ্ছে (Merging)... দয়া করে অপেক্ষা করুন।")
    
    output_filename = f"final_{chat_id}.mp4"
    list_filename = f"list_{chat_id}.txt"

    try:
        # FFmpeg লিস্ট ফাইল তৈরি
        with open(list_filename, "w") as f:
            for path in user_data[chat_id]:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # FFmpeg কমান্ড (ভিডিওর কোয়ালিটি ঠিক রেখে দ্রুত মার্জ করবে)
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", list_filename, "-c", "copy", output_filename
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode != 0:
            raise Exception("FFmpeg Error: " + process.stderr)

        # আপলোড করা
        await status_msg.edit_text("📤 আপলোড শুরু হচ্ছে...")
        start_time = time.time()
        
        await message.reply_video(
            video=output_filename,
            caption="🎬 আপনার সম্পূর্ণ ভিডিও তৈরি হয়ে গেছে!",
            progress=progress_bar,
            progress_args=(status_msg, start_time, "📤 আপলোড হচ্ছে...")
        )

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")
    
    finally:
        # ফাইল পরিষ্কার করা
        if os.path.exists(list_filename): os.remove(list_filename)
        if os.path.exists(output_filename): os.remove(output_filename)
        for path in user_data.get(chat_id, []):
            if os.path.exists(path): os.remove(path)
        user_data[chat_id] = []

print("বটটি চালু হয়েছে...")
app.run()
