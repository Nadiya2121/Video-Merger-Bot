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

# --- ফাংশন ১: ভিডিওর সঠিক সময় (ডিউরেশন) বের করা ---
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

# --- ফাংশন ২: উন্নত প্রোগ্রেস বার (এরর হ্যান্ডলিং ও ডিটেইলস সহ) ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    # প্রতি ৫ সেকেন্ড পরপর আপডেট হবে যাতে টেলিগ্রাম ফ্লাড না করে
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

# --- ফাংশন ৩: প্রসেসিং হার্টবিট (ফেসবুক এডিটিংয়ের সময় টাইমার দেখানোর জন্য) ---
async def edit_heartbeat(status_msg, start_time):
    # এই টাস্কটি ভিডিও রেন্ডার হওয়ার সময় ইউজারকে টাইমার দেখাবে
    icons = ["⚙️", "🪄", "⏳", "⌛"]
    idx = 0
    try:
        while True:
            elapsed = round(time.time() - start_time)
            icon = icons[idx % 4]
            text = (f"{icon} **ফেসবুক স্টাইলে সুপার ফাস্ট প্রসেস হচ্ছে...**\n\n"
                    f"⏱ সময় অতিবাহিত: {elapsed} সেকেন্ড\n"
                    f"🚀 আল্ট্রাফাস্ট এনকোডিং মোড চালু করা হয়েছে।\n"
                    f"⚠️ ৫১২এমবি র‍্যামে সেরা পারফরম্যান্সের জন্য প্রসেসিং চলছে।")
            await status_msg.edit_text(text)
            idx += 1
            await asyncio.sleep(8) # প্রতি ৮ সেকেন্ডে একবার আপডেট
    except Exception:
        pass

# --- ৪. স্টার্ট কমান্ড (বিস্তারিত গাইড) ---
@app.on_message(filters.command("start"))
async def start(client, message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "files": [], 
        "total_size": 0, 
        "thumb": None, 
        "music": None,
        "state": "none",
        "filename": f"final_video_{chat_id}.mp4"
    }
    
    welcome_text = (
        "👋 **প্রো ভিডিও এডিটর ও মার্জার বটে স্বাগতম!**\n\n"
        "আমি আপনার ভিডিওর সব কাজ নিখুঁতভাবে করতে পারি।\n\n"
        "🎬 **১. ভিডিও জোড়া লাগানো (Merge Mode):**\n"
        "সরাসরি ভিডিওগুলো পাঠান। সব পাঠানো শেষ হলে **Done** লিখুন।\n\n"
        "🚀 **২. ফেসবুক শর্টস এডিট (Facebook Mode):**\n"
        "১. মিউজিক ফাইলের রিপ্লাইতে লিখুন `/setmusic`।\n"
        "২. এরপর ফেসবুক এডিট করতে আগে লিখুন **/edit**।\n"
        "৩. তারপর ভিডিওটি পাঠান। আমি অটো মিউজিক ও ফিল্টার লাগিয়ে দেব।\n\n"
        "⚙️ **অন্যান্য কমান্ড:**\n"
        "✏️ **/setname** - মার্জ করা ফাইলের নাম সেট করুন।\n"
        "❌ **/cancel** - সব বাতিল এবং ফাইল ডিলিট করুন।"
    )
    await message.reply_text(welcome_text)

# --- ৫. মিউজিক সেট করার কমান্ড ---
@app.on_message(filters.command("setmusic"))
async def set_music(client, message):
    chat_id = message.chat.id
    if not message.reply_to_message or not (message.reply_to_message.audio or message.reply_to_message.voice):
        await message.reply_text("❌ অডিও বা ভয়েস ফাইলের রিপ্লাইতে `/setmusic` লিখুন।")
        return
    
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "music": None, "state": "none"}
    
    status = await message.reply_text("🎵 ব্যাকগ্রাউন্ড মিউজিক সেভ হচ্ছে...")
    music_path = await message.reply_to_message.download(file_name=f"downloads/{chat_id}_bgm.mp3")
    user_data[chat_id]["music"] = music_path
    await status.edit_text("✅ মিউজিক সেভ হয়েছে! এখন ফেসবুক এডিট করতে চাইলে **/edit** লিখে ভিডিও পাঠান।")

# --- ৬. ফেসবুক এডিট মোড চালু ---
@app.on_message(filters.command("edit"))
async def activate_edit_mode(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data or not user_data[chat_id].get("music"):
        await message.reply_text("❌ আগে অডিও সেট করুন। অডিওর রিপ্লাইতে লিখুন `/setmusic`।")
        return
    
    user_data[chat_id]["state"] = "waiting_for_edit"
    await message.reply_text("🪄 **ফেসবুক এডিট মোড চালু!**\nএখন আপনার শর্টস ভিডিওটি পাঠান। আমি এটিতে সাউন্ড ও কালার ফিল্টার লাগিয়ে দেব।")

# --- ৭. থাম্বনেইল সেট করা ---
@app.on_message(filters.photo)
async def handle_thumb(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None}
    
    if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
        os.remove(user_data[chat_id]["thumb"])

    status = await message.reply_text("📸 থাম্বনেইল ডাউনলোড হচ্ছে...")
    path = await message.download(file_name=f"downloads/{chat_id}_thumb.jpg")
    user_data[chat_id]["thumb"] = path
    await status.edit_text("✅ থাম্বনেইল সেট হয়েছে!")

# --- ৮. নাম সেট করা ---
@app.on_message(filters.command("setname"))
async def set_name(client, message):
    chat_id = message.chat.id
    if len(message.command) > 1:
        new_name = message.text.split(None, 1)[1]
        if not new_name.endswith(".mp4"): new_name += ".mp4"
        if chat_id not in user_data: user_data[chat_id] = {"files": [], "total_size": 0}
        user_data[chat_id]["filename"] = new_name
        await message.reply_text(f"✅ নাম সেট করা হয়েছে: `{new_name}`")
    else:
        await message.reply_text("উদাহরণ: `/setname My_Movie.mp4`")

# --- ৯. বাতিল করা ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        for path in user_data[chat_id].get("files", []):
            if os.path.exists(path): os.remove(path)
        if user_data[chat_id].get("music") and os.path.exists(user_data[chat_id]["music"]):
            os.remove(user_data[chat_id]["music"])
        del user_data[chat_id]
        await message.reply_text("❌ সব বাতিল এবং ফাইল মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("কোনো প্রসেস রানিং নেই।")

# --- ১০. ভিডিও হ্যান্ডলার (সবচেয়ে গুরুত্বপূর্ণ অংশ) ---
@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "state": "none", "filename": f"final_{chat_id}.mp4"}

    # ক) যদি এটি ফেসবুক এডিটের ভিডিও হয়
    if user_data[chat_id].get("state") == "waiting_for_edit":
        user_data[chat_id]["state"] = "none" # রিসেট
        status_msg = await message.reply_text("📥 এডিটিংয়ের জন্য ভিডিও ডাউনলোড হচ্ছে...", quote=True)
        start_time = time.time()
        
        v_path = await message.download(
            progress=progress_bar, 
            progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
        )
        
        # প্রসেসিং হার্টবিট শুরু
        edit_start_time = time.time()
        heartbeat_task = asyncio.create_task(edit_heartbeat(status_msg, edit_start_time))
        
        out_v = f"fb_edit_{chat_id}_{time.time()}.mp4"
        bgm = user_data[chat_id]["music"]
        
        # --- নতুন সুপার ফাস্ট কমান্ড (৫১২ এমবি র‍্যাম ও স্পিডের জন্য) ---
        cmd = [
            "ffmpeg", "-y", "-i", v_path, "-i", bgm,
            "-filter_complex", 
            # র‍্যাম বাঁচাতে রেজোলিউশন ৭২০পি করা হয়েছে ও কালার টিউন করা হয়েছে
            "[0:v]scale=-2:720,eq=saturation=1.4:contrast=1.2:brightness=0.03[v];"
            "[0:a]volume=1.8[a1];"
            "[1:a]volume=0.03[a2];"
            "[a1][a2]amix=inputs=2:duration=first[a]",
            "-map", "[v]", "-map", "[a]", 
            "-c:v", "libx264", 
            "-preset", "ultrafast",  # ফাস্ট রেন্ডারিংয়ের জন্য
            "-crf", "28",            # সাইজ ও র‍্যাম ম্যানেজমেন্ট
            "-threads", "0",         # সব CPU কোর ব্যবহারের জন্য
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", 
            out_v
        ]
        
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        
        # রেন্ডার শেষ হলে হার্টবিট বন্ধ করা
        heartbeat_task.cancel()

        duration = get_video_duration(out_v)
        await status_msg.edit_text("📤 এডিট সম্পন্ন! এখন আপলোড হচ্ছে...")
        
        await message.reply_video(
            video=out_v, 
            duration=duration, 
            caption="🎬 **আপনার ফেসবুক শর্টস ভিডিও রেডি!**\n\n(সাউন্ড ও কালার সুপার ফাস্ট মোডে টিউন করা হয়েছে)",
            thumb=user_data[chat_id].get("thumb"),
            progress=progress_bar,
            progress_args=(status_msg, time.time(), "📤 আপলোড হচ্ছে...")
        )
        
        if os.path.exists(v_path): os.remove(v_path)
        if os.path.exists(out_v): os.remove(out_v)
        await status_msg.delete()
        return

    # খ) সাধারণ মার্জিং মোড
    if user_data[chat_id]["total_size"] >= MAX_LIMIT:
        await message.reply_text("⚠️ লিমিট শেষ! আপনি ২জিবি পূর্ণ করে ফেলেছেন। এখন **Done** লিখুন।")
        return

    status_msg = await message.reply_text("📥 ভিডিওটি মার্জ লিস্টে যুক্ত হচ্ছে...", quote=True)
    start_time = time.time()
    
    file_path = await message.download(
        progress=progress_bar,
        progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
    )

    f_size = os.path.getsize(file_path)
    user_data[chat_id]["files"].append(file_path)
    user_data[chat_id]["total_size"] += f_size

    # বিস্তারিত স্টোরেজ রিপোর্ট
    used_mb = user_data[chat_id]["total_size"] / (1024 * 1024)
    remaining_mb = (MAX_LIMIT - user_data[chat_id]["total_size"]) / (1024 * 1024)

    await status_msg.edit_text(
        f"✅ এপিসোড {len(user_data[chat_id]['files'])} যুক্ত হয়েছে।\n\n"
        f"📊 **স্টোরেজ রিপোর্ট:**\n"
        f"মোট পাঠানো হয়েছে: {used_mb:.2f} MB\n"
        f"খালি আছে: **{remaining_mb:.2f} MB**\n\n"
        f"পরেরটি পাঠান অথবা **Done** লিখুন।"
    )

# --- ১১. মার্জিং শেষ করা (Done কমান্ড) ---
@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos_done(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data or len(user_data[chat_id]["files"]) < 2:
        await message.reply_text("❌ মার্জ করতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("⚙️ ভিডিওগুলো জোড়া লাগানো হচ্ছে... একটু অপেক্ষা করুন।")
    output_filename = user_data[chat_id].get("filename", f"merged_{chat_id}.mp4")
    list_filename = f"list_{chat_id}.txt"

    try:
        with open(list_filename, "w") as f:
            for path in user_data[chat_id]["files"]:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # ফাস্ট কপি মার্জ
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_filename, "-c", "copy", "-movflags", "+faststart", output_filename]
        merge_process = subprocess.run(cmd, capture_output=True, text=True)

        # ফরম্যাট আলাদা হলে এনকোডিং (এখানেও আল্ট্রাফাস্ট দেওয়া হয়েছে স্পিডের জন্য)
        if merge_process.returncode != 0:
            await status_msg.edit_text("⚠️ ফরম্যাট আলাদা হওয়ায় এনকোডিং হচ্ছে (সময় লাগবে)...")
            cmd_encode = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_filename, "-c:v", "libx264", "-preset", "ultrafast", "-threads", "0", "-movflags", "+faststart", output_filename]
            subprocess.run(cmd_encode, check=True)

        duration = get_video_duration(output_filename)
        await status_msg.edit_text("📤 মার্জ শেষ! এখন আপলোড হচ্ছে...")
        
        video_caption = (
            f"🎬 **ফাইল নেম:** `{output_filename}`\n\n"
            f"✅ **মোট ফাইল:** {len(user_data[chat_id]['files'])}\n"
            f"📊 **সাইজ:** {os.path.getsize(output_filename)/(1024*1024):.2f} MB\n"
            f"⏳ **সময়:** {time.strftime('%H:%M:%S', time.gmtime(duration))}"
        )

        start_time = time.time()
        await message.reply_video(
            video=output_filename,
            duration=duration,
            thumb=user_data[chat_id].get("thumb"),
            caption=video_caption,
            progress=progress_bar,
            progress_args=(status_msg, start_time, "📤 আপলোড হচ্ছে...")
        )
        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")
    
    finally:
        # সব ক্লিয়ার করা
        if os.path.exists(list_filename): os.remove(list_filename)
        if os.path.exists(output_filename): os.remove(output_filename)
        if chat_id in user_data:
            for path in user_data[chat_id].get("files", []):
                if os.path.exists(path): os.remove(path)
            user_data[chat_id]["files"] = []
            user_data[chat_id]["total_size"] = 0

print("🚀 বটটি বিস্তারিত ফিচার ও সুপার ফাস্ট স্পিডসহ পূর্ণাঙ্গভাবে সচল!")
app.run()
