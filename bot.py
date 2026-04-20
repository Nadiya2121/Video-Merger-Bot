import os
import time
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import MessageNotModified, FloodWait

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

# --- উন্নত প্রোগ্রেস বার ফাংশন (এরর হ্যান্ডলিং সহ) ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    # প্রতি ৫ সেকেন্ড পর পর বা ডাউনলোড শেষে প্রোগ্রেস আপডেট হবে (FloodWait এড়াতে)
    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / (diff if diff > 0 else 1)
        
        progress = "[{0}{1}]".format(
            ''.join(["■" for i in range(int(percentage / 10))]),
            ''.join(["□" for i in range(10 - int(percentage / 10))])
        )
        
        tmp = (f"**{action}**\n\n"
               f"{progress} {round(percentage, 2)}%\n"
               f"📊 সাইজ: {current/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n"
               f"🚀 স্পিড: {speed/1024:.2f} KB/s")
        
        try:
            await status_msg.edit_text(tmp)
        except MessageNotModified:
            pass
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
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
    
    welcome_text = (
        "👋 **ভিডিও মার্জার বটে স্বাগতম!**\n\n"
        "আমি আপনার ভিডিওগুলো সিরিয়াল অনুযায়ী নিখুঁতভাবে জোড়া লাগিয়ে দিতে পারি।\n\n"
        "🛠 **কিভাবে ব্যবহার করবেন?**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ একে একে আপনার ভিডিওগুলো পাঠান (এপিসোড ১, ২, ৩...)।\n"
        "2️⃣ থাম্বনেইল হিসেবে ব্যবহার করতে একটি **ছবি (Photo)** পাঠান।\n"
        "3️⃣ ফাইলের নাম দিতে চাইলে লিখুন: `/setname নাম`।\n"
        "4️⃣ সব শেষে **Done** লিখে মেসেজ দিন।\n\n"
        "⚠️ **সীমাবদ্ধতা:** ২জিবি (2GB) পর্যন্ত ভিডিও যোগ করা যাবে।\n"
        "❌ **বাতিল:** ভুল হলে **/cancel** লিখুন।\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply_text(welcome_text)

# --- ২. ক্যানসেল কমান্ড ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        # সব টেম্পোরারি ভিডিও ফাইল মুছে ফেলা
        for path in user_data[chat_id]["files"]:
            if os.path.exists(path): os.remove(path)
        # থাম্বনেইল মুছে ফেলা
        if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
            os.remove(user_data[chat_id]["thumb"])
        
        del user_data[chat_id]
        await message.reply_text("❌ আপনার বর্তমান প্রসেসটি বাতিল এবং সব ফাইল মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("আপনার কোনো প্রসেস বর্তমানে রানিং নেই।")

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
        await message.reply_text("সঠিক নিয়ম: `/setname My_Movie_Name`")

# --- ৪. থাম্বনেইল হ্যান্ডলার ---
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
    await status.edit_text("✅ থাম্বনেইল সেট করা হয়েছে! এটি ভিডিওর কভারে যুক্ত হবে।")

# --- ৫. ভিডিও হ্যান্ডলার (স্টোরেজ ট্র্যাকার সহ) ---
@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "filename": f"final_video_{chat_id}.mp4"}

    # ২জিবি লিমিট চেক
    if user_data[chat_id]["total_size"] >= MAX_LIMIT:
        await message.reply_text("⚠️ লিমিট শেষ! আপনি ইতিমধ্যে ২জিবি ভিডিও ফাইল দিয়ে ফেলেছেন। এখন **Done** লিখে মার্জ করুন।")
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

    # কতটুকু খালি আছে তা বের করা
    used_mb = user_data[chat_id]["total_size"] / (1024 * 1024)
    remaining_mb = (MAX_LIMIT - user_data[chat_id]["total_size"]) / (1024 * 1024)

    await status_msg.edit_text(
        f"✅ এপিসোড {len(user_data[chat_id]['files'])} যুক্ত হয়েছে।\n\n"
        f"📊 **স্টোরেজ রিপোর্ট:**\n"
        f"মোট ব্যবহৃত: {used_mb:.2f} MB\n"
        f"খালি আছে: **{remaining_mb:.2f} MB**\n\n"
        f"পরেরটি পাঠান অথবা **Done** লিখুন।"
    )

# --- ৬. ভিডিও মার্জিং এবং আপলোড (সব ফিক্স সহ) ---
@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos(client, message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or len(user_data[chat_id]["files"]) < 2:
        await message.reply_text("❌ ভিডিও জোড়া লাগাতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("⚙️ ভিডিও জোড়া লাগানো হচ্ছে... একটু অপেক্ষা করুন।")
    
    # ভিডিওর ফাইনাল নাম ঠিক করা
    output_filename = user_data[chat_id].get("filename", f"merged_{chat_id}.mp4")
    list_filename = f"list_{chat_id}.txt"

    try:
        # FFmpeg-এর জন্য ভিডিও লিস্ট ফাইল তৈরি
        with open(list_filename, "w") as f:
            for path in user_data[chat_id]["files"]:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # ধাপ ১: ভিডিও কনক্যাট (Copy Mode - সুপার ফাস্ট)
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_filename, "-c", "copy", "-movflags", "+faststart", output_filename
        ]
        
        merge_process = subprocess.run(cmd, capture_output=True, text=True)

        # যদি ফরম্যাট ভিন্ন হওয়ার কারণে কপি মোড ফেল করে, তবে এনকোড করা
        if merge_process.returncode != 0:
            await status_msg.edit_text("⚠️ ফরম্যাট ভিন্ন হওয়ায় এনকোডিং হচ্ছে (এতে সময় বেশি লাগবে)...")
            cmd_encode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_filename, "-movflags", "+faststart", output_filename
            ]
            subprocess.run(cmd_encode, check=True)

        # ভিডিওর মোট দৈর্ঘ্য (সময়) বের করা
        duration = get_video_duration(output_filename)

        await status_msg.edit_text("📤 মার্জ শেষ! এখন আপলোড হচ্ছে... দয়া করে অপেক্ষা করুন।")
        
        # ফাইনাল ক্যাপশন সেট করা
        video_caption = (
            f"🎬 **ফাইল নাম:** `{output_filename}`\n\n"
            f"✅ **মোট ফাইল:** {len(user_data[chat_id]['files'])}\n"
            f"📊 **সাইজ:** {os.path.getsize(output_filename)/(1024*1024):.2f} MB\n"
            f"⏳ **সময়:** {time.strftime('%H:%M:%S', time.gmtime(duration))}"
        )

        start_time = time.time()
        
        # ভিডিও আপলোড
        await message.reply_video(
            video=output_filename,
            duration=duration,
            thumb=user_data[chat_id]["thumb"],
            caption=video_caption,
            progress=progress_bar,
            progress_args=(status_msg, start_time, "📤 আপলোড হচ্ছে...")
        )

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")
    
    finally:
        # সব টেম্পোরারি ফাইল এবং ইউজারের ডেটা মুছে ফেলা
        if os.path.exists(list_filename): os.remove(list_filename)
        if os.path.exists(output_filename): os.remove(output_filename)
        if chat_id in user_data:
            for path in user_data[chat_id]["files"]:
                if os.path.exists(path): os.remove(path)
            if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
                os.remove(user_data[chat_id]["thumb"])
            del user_data[chat_id]

print("🔥 বটটি এখন সব ফিচার (ফাইল নেম, থাম্বনেইল, স্টোরেজ ট্র্যাকার) সহ রানিং!")
app.run()
