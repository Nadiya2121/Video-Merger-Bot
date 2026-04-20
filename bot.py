import os
import time
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# FFmpeg অটো-সেটআপ (সার্ভারের এরর বন্ধ করতে)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# --- আপনার ভেরিয়েবলসমূহ ---
API_ID = "19234664"
API_HASH = "29c2f3b3d115cf1b0231d816deb271f5"
BOT_TOKEN = "8710959010:AAHfutLem56XMMvNN9GG6n-xwJUiKYA2J7s"
MAX_LIMIT = 2000 * 1024 * 1024  # ২জিবি লিমিট (বাইটসে)

app = Client("video_merger", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ইউজার ডাটা স্টোর করার ডিকশনারি
user_data = {}

# ডাউনলোড ফোল্ডার নিশ্চিত করা
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- ভিডিওর সঠিক সময় বের করার ফাংশন ---
def get_video_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return int(float(result.stdout.strip()))
    except Exception:
        return 0

# --- প্রোগ্রেস বার ফাংশন ---
def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / (diff if diff > 0 else 1)
        
        progress = "[{0}{1}]".format(
            ''.join(["■" for i in range(int(percentage / 10))]),
            ''.join(["□" for i in range(10 - int(percentage / 10))])
        )
        
        tmp = f"**{action}**\n\n{progress} {round(percentage, 2)}%\n" \
              f"📊 সাইজ: {current/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n" \
              f"🚀 স্পিড: {speed/1024:.2f} KB/s"
        
        try:
            status_msg.edit_text(tmp)
        except:
            pass

# --- ১. স্টার্ট কমান্ড ---
@app.on_message(filters.command("start"))
async def start(client, message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "files": [], 
        "total_size": 0, 
        "thumb": None, 
        "filename": f"final_video_{chat_id}.mp4"
    }
    await message.reply_text(
        "👋 **ভিডিও মার্জার বটে স্বাগতম!**\n\n"
        "**কিভাবে ব্যবহার করবেন?**\n"
        "১. সিরিয়াল অনুযায়ী ভিডিওগুলো পাঠান।\n"
        "২. ভিডিওর কভার ফটো দিতে একটি **Photo** পাঠান।\n"
        "৩. নাম বদলাতে চাইলে লিখুন: `/setname MyMovie` \n"
        "৪. সব শেষে **Done** লিখে মেসেজ দিন।\n\n"
        "❌ বাতিল করতে চাইলে লিখুন: **/cancel**"
    )

# --- ২. ক্যানসেল কমান্ড (পুরো প্রসেস ডিলিট) ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        # ফাইলগুলো ডিলিট করা
        for path in user_data[chat_id]["files"]:
            if os.path.exists(path): os.remove(path)
        # থাম্বনেইল ডিলিট
        if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
            os.remove(user_data[chat_id]["thumb"])
        
        del user_data[chat_id]
        await message.reply_text("❌ আপনার বর্তমান প্রসেসটি বাতিল এবং সব ফাইল মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("আপনার কোনো প্রসেস রানিং নেই।")

# --- ৩. কাস্টম নাম সেট করা ---
@app.on_message(filters.command("setname"))
async def set_name(client, message):
    chat_id = message.chat.id
    if len(message.command) > 1:
        new_name = message.text.split(None, 1)[1]
        if not new_name.endswith(".mp4"):
            new_name += ".mp4"
        
        if chat_id not in user_data:
            user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None}
        
        user_data[chat_id]["filename"] = new_name
        await message.reply_text(f"✅ আউটপুট ভিডিওর নাম সেট করা হয়েছে:\n`{new_name}`")
    else:
        await message.reply_text("সঠিক নিয়ম: `/setname My_Video_Name`")

# --- ৪. থাম্বনেইল হ্যান্ডলার (ছবি পাঠালে থাম্বনেইল হবে) ---
@app.on_message(filters.photo)
async def handle_thumb(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "filename": f"final_video_{chat_id}.mp4"}
    
    # আগের থাম্বনেইল থাকলে ডিলিট করা
    if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
        os.remove(user_data[chat_id]["thumb"])

    status = await message.reply_text("📸 থাম্বনেইল প্রসেস হচ্ছে...")
    path = await message.download(file_name=f"downloads/{chat_id}_thumb.jpg")
    user_data[chat_id]["thumb"] = path
    await status.edit_text("✅ থাম্বনেইল সেট করা হয়েছে! ভিডিওর সাথে এটি যুক্ত হবে।")

# --- ৫. ভিডিও হ্যান্ডলার (স্টোরেজ ট্র্যাকার সহ) ---
@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "filename": f"final_video_{chat_id}.mp4"}

    # ২জিবি লিমিট চেক
    if user_data[chat_id]["total_size"] >= MAX_LIMIT:
        await message.reply_text("⚠️ লিমিট শেষ! আপনি ইতিমধ্যে ২জিবি ফাইল দিয়ে ফেলেছেন। এখন **Done** লিখে মার্জ করুন।")
        return

    status_msg = await message.reply_text("📥 ভিডিওটি ডাউনলোড হচ্ছে...", quote=True)
    start_time = time.time()

    # ইউজারের সাব-ফোল্ডার
    user_dir = f"downloads/{chat_id}"
    if not os.path.exists(user_dir): os.makedirs(user_dir)

    file_path = await message.download(
        file_name=f"{user_dir}/{time.time()}.mp4",
        progress=progress_bar,
        progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
    )

    # সাইজ হিসাব করা
    f_size = os.path.getsize(file_path)
    user_data[chat_id]["files"].append(file_path)
    user_data[chat_id]["total_size"] += f_size

    # কতটুকু খালি আছে বের করা
    used_mb = user_data[chat_id]["total_size"] / (1024 * 1024)
    remaining_mb = (MAX_LIMIT - user_data[chat_id]["total_size"]) / (1024 * 1024)

    await status_msg.edit_text(
        f"✅ এপিসোড {len(user_data[chat_id]['files'])} যুক্ত হয়েছে।\n\n"
        f"📊 **স্টোরেজ রিপোর্ট:**\n"
        f"মোট পাঠানো হয়েছে: {used_mb:.2f} MB\n"
        f"বাকি আছে: **{remaining_mb:.2f} MB**\n\n"
        f"পরেরটি পাঠান অথবা **Done** লিখুন।"
    )

# --- ৬. ভিডিও মার্জিং (Done কমান্ড) ---
@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos(client, message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or len(user_data[chat_id]["files"]) < 2:
        await message.reply_text("❌ ভিডিও জোড়া লাগাতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("⚙️ ভিডিওগুলো জোড়া লাগানো হচ্ছে... দয়া করে একটু অপেক্ষা করুন।")
    
    output_filename = user_data[chat_id]["filename"]
    list_filename = f"list_{chat_id}.txt"

    try:
        # FFmpeg লিস্ট তৈরি
        with open(list_filename, "w") as f:
            for path in user_data[chat_id]["files"]:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # ধাপ ১: কনক্যাট (Fast Copy)
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_filename, "-c", "copy", "-movflags", "+faststart", output_filename
        ]
        
        merge_process = subprocess.run(cmd, capture_output=True, text=True)

        # যদি কপি মোড ফেল করে (ভিন্ন রেজোলিউশন হলে)
        if merge_process.returncode != 0:
            await status_msg.edit_text("⚠️ ফরম্যাট ভিন্ন হওয়ায় ভিডিও এনকোড হচ্ছে (সময় লাগবে)...")
            cmd_encode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_filename, "-movflags", "+faststart", output_filename
            ]
            subprocess.run(cmd_encode, check=True)

        # ডিউরেশন বের করা
        duration = get_video_duration(output_filename)

        # আপলোড করা
        await status_msg.edit_text("📤 মার্জ সম্পন্ন! এখন আপলোড হচ্ছে...")
        start_time = time.time()
        
        await message.reply_video(
            video=output_filename,
            duration=duration,
            thumb=user_data[chat_id]["thumb"], # থাম্বনেইল এখানে যুক্ত হবে
            caption=f"🎬 **আপনার মার্জ করা ভিডিও!**\n\n✅ মোট ফাইল: {len(user_data[chat_id]['files'])}\n📊 সাইজ: {os.path.getsize(output_filename)/(1024*1024):.2f} MB\n⏳ সময়: {time.strftime('%H:%M:%S', time.gmtime(duration))}",
            progress=progress_bar,
            progress_args=(status_msg, start_time, "📤 আপলোড হচ্ছে...")
        )

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")
    
    finally:
        # ক্লিনিং
        if os.path.exists(list_filename): os.remove(list_filename)
        if os.path.exists(output_filename): os.remove(output_filename)
        if chat_id in user_data:
            for path in user_data[chat_id]["files"]:
                if os.path.exists(path): os.remove(path)
            if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
                os.remove(user_data[chat_id]["thumb"])
            del user_data[chat_id]

print("🚀 বটটি এখন সব ফিচার (Thumbnail, Storage Tracker, Custom Name) সহ রানিং!")
app.run()
