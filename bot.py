import os
import time
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import MessageNotModified, FloodWait

# FFmpeg অটো-সেটআপ
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

# --- অ্যাবসলিউট ডাউনলোড ডিরেক্টরি পাথ সেটআপ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- ভিডিওতে অডিও ট্র্যাক আছে কিনা তা চেক করার ফাংশন ---
def has_audio(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a", 
            "-show_entries", "stream=codec_name", "-of", "csv=p=0", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except Exception:
        return False

# --- ভিডিওর সঠিক সময় (ডিউরেশন) বের করা ---
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

# --- ভিডিও স্ট্যান্ডার্ডাইজ করার অপ্টিমাইজড ও দ্রুতগতির ফাংশন ---
async def normalize_video(input_path, output_path):
    audio_present = has_audio(input_path)
    
    # -threads 0 এবং -sws_flags fast_bilinear ব্যবহারের মাধ্যমে প্রসেসিং স্পিড বাড়ানো হয়েছে
    if audio_present:
        cmd = [
            "ffmpeg", "-y", 
            "-threads", "0",
            "-sws_flags", "fast_bilinear",
            "-i", input_path,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r", "30",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "32",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            output_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y", 
            "-threads", "0",
            "-sws_flags", "fast_bilinear",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", 
            "-i", input_path,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r", "30",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "32",
            "-c:a", "aac", "-shortest",
            output_path
        ]
        
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return process.returncode == 0

# --- উন্নত প্রোগ্রেস বার ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
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

# --- প্রসেসিং হার্টবিট ---
async def edit_heartbeat(status_msg, start_time):
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
            await asyncio.sleep(8)
    except Exception:
        pass

# --- স্টার্ট কমান্ড ---
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

# --- মিউজিক সেট করার কমান্ড ---
@app.on_message(filters.command("setmusic"))
async def set_music(client, message):
    chat_id = message.chat.id
    if not message.reply_to_message or not (message.reply_to_message.audio or message.reply_to_message.voice):
        await message.reply_text("❌ অডিও বা ভয়েস ফাইলের রিপ্লাইতে `/setmusic` লিখুন।")
        return
    
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "music": None, "state": "none"}
    
    status = await message.reply_text("🎵 ব্যাকগ্রাউন্ড মিউজিক সেভ হচ্ছে...")
    music_filename = os.path.join(DOWNLOAD_DIR, f"{chat_id}_bgm.mp3")
    music_path = await message.reply_to_message.download(file_name=music_filename)
    user_data[chat_id]["music"] = music_path
    await status.edit_text("✅ মিউজিক সেভ হয়েছে! এখন ফেসবুক এডিট করতে চাইলে **/edit** লিখে ভিডিও পাঠান।")

# --- ফেসবুক এডিট মোড চালু ---
@app.on_message(filters.command("edit"))
async def activate_edit_mode(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data or not user_data[chat_id].get("music"):
        await message.reply_text("❌ আগে অডিও সেট করুন। অডিওর রিপ্লাইতে লিখুন `/setmusic`।")
        return
    
    user_data[chat_id]["state"] = "waiting_for_edit"
    await message.reply_text("🪄 **ফেসবুক এডিট মোড চালু!**\nএখন আপনার শর্টস ভিডিওটি পাঠান। আমি এটিটিতে সাউন্ড ও কালার ফিল্টার লাগিয়ে দেব।")

# --- থাম্বনেইল সেট করা ---
@app.on_message(filters.photo)
async def handle_thumb(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None}
    
    if user_data[chat_id]["thumb"] and os.path.exists(user_data[chat_id]["thumb"]):
        try:
            os.remove(user_data[chat_id]["thumb"])
        except Exception:
            pass

    status = await message.reply_text("📸 থাম্বনেইল ডাউনলোড হচ্ছে...")
    thumb_path = os.path.join(DOWNLOAD_DIR, f"{chat_id}_thumb.jpg")
    try:
        path = await message.download(file_name=thumb_path)
        user_data[chat_id]["thumb"] = path
        await status.edit_text("✅ থাম্বনেইল সেট হয়েছে!")
    except Exception as e:
        await status.edit_text(f"❌ থাম্বনেইল সেভ করতে সমস্যা হয়েছে: {str(e)}")

# --- নাম সেট করা ---
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

# --- বাতিল করা ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        for path in user_data[chat_id].get("files", []):
            if os.path.exists(path): os.remove(path)
        if user_data[chat_id].get("music") and os.path.exists(user_data[chat_id]["music"]):
            os.remove(user_data[chat_id]["music"])
        if user_data[chat_id].get("thumb") and os.path.exists(user_data[chat_id]["thumb"]):
            os.remove(user_data[chat_id]["thumb"])
        del user_data[chat_id]
        await message.reply_text("❌ সব বাতিল এবং ফাইল মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("কোনো প্রসেস রানিং নেই।")

# --- ভিডিও হ্যান্ডলার ---
@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "state": "none", "filename": f"final_{chat_id}.mp4"}

    # ক) ফেসবুক এডিট মোড
    if user_data[chat_id].get("state") == "waiting_for_edit":
        user_data[chat_id]["state"] = "none"
        status_msg = await message.reply_text("📥 এডিটিংয়ের জন্য ভিডিও ডাউনলোড হচ্ছে...", quote=True)
        start_time = time.time()
        
        video_download_path = os.path.join(DOWNLOAD_DIR, f"fb_dl_{chat_id}_{time.time()}")
        v_path = await message.download(
            file_name=video_download_path,
            progress=progress_bar, 
            progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
        )
        
        edit_start_time = time.time()
        heartbeat_task = asyncio.create_task(edit_heartbeat(status_msg, edit_start_time))
        
        out_v = os.path.join(DOWNLOAD_DIR, f"fb_edit_{chat_id}_{time.time()}.mp4")
        bgm = user_data[chat_id]["music"]
        
        cmd = [
            "ffmpeg", "-y", 
            "-threads", "0",
            "-sws_flags", "fast_bilinear",
            "-i", v_path, "-i", bgm,
            "-filter_complex", 
            "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,eq=saturation=1.4:contrast=1.2:brightness=0.03[v];"
            "[0:a]volume=1.8[a1];"
            "[1:a]volume=0.03[a2];"
            "[a1][a2]amix=inputs=2:duration=first[a]",
            "-map", "[v]", "-map", "[a]", 
            "-c:v", "libx264", 
            "-preset", "ultrafast",  
            "-crf", "32",            
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", 
            out_v
        ]
        
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        
        heartbeat_task.cancel()

        duration = get_video_duration(out_v)
        await status_msg.edit_text("📤 এডিট সম্পন্ন! এখন আপলোড হচ্ছে...")
        
        await message.reply_video(
            video=out_v, 
            duration=duration, 
            caption="🎬 **আপনার ফেসবুক শর্টস ভিডিও রেডি!**\n\n(সাউন্ড ও কালার টিউন করা হয়েছে)",
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

    status_msg = await message.reply_text("📥 ভিডিওটি ডাউনলোড করা হচ্ছে...", quote=True)
    start_time = time.time()
    
    video_download_path = os.path.join(DOWNLOAD_DIR, f"merge_dl_{chat_id}_{time.time()}")
    file_path = await message.download(
        file_name=video_download_path,
        progress=progress_bar,
        progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
    )

    # স্ট্যান্ডার্ড ফরম্যাটে দ্রুত রূপান্তর
    await status_msg.edit_text("⚙️ ভিডিও ফরম্যাট স্ট্যান্ডার্ডাইজ করা হচ্ছে...")
    norm_file_path = os.path.join(DOWNLOAD_DIR, f"norm_{chat_id}_{time.time()}.mp4")
    
    is_normalized = await normalize_video(file_path, norm_file_path)
    
    if os.path.exists(file_path): 
        os.remove(file_path)
        
    if is_normalized and os.path.exists(norm_file_path):
        final_file_path = norm_file_path
    else:
        final_file_path = file_path

    f_size = os.path.getsize(final_file_path)
    user_data[chat_id]["files"].append(final_file_path)
    user_data[chat_id]["total_size"] += f_size

    used_mb = user_data[chat_id]["total_size"] / (1024 * 1024)
    remaining_mb = (MAX_LIMIT - user_data[chat_id]["total_size"]) / (1024 * 1024)

    await status_msg.edit_text(
        f"✅ এপিসোড {len(user_data[chat_id]['files'])} যুক্ত হয়েছে (ফরম্যাট চেক সম্পূর্ণ)।\n\n"
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
    output_filename = os.path.join(DOWNLOAD_DIR, user_data[chat_id].get("filename", f"merged_{chat_id}.mp4"))
    list_filename = os.path.join(DOWNLOAD_DIR, f"list_{chat_id}.txt")

    try:
        with open(list_filename, "w") as f:
            for path in user_data[chat_id]["files"]:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # দ্রুত কপি মার্জিং
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_filename, "-c", "copy", "-movflags", "+faststart", output_filename]
        merge_process = subprocess.run(cmd, capture_output=True, text=True)

        if merge_process.returncode != 0:
            await status_msg.edit_text("⚠️ প্রথম ধাপে সমস্যা হয়েছে, পুনরায় এনকোড করে ট্রাই করা হচ্ছে...")
            cmd_encode = [
                "ffmpeg", "-y", 
                "-threads", "0",
                "-f", "concat", "-safe", "0", "-i", list_filename, 
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "32", 
                "-movflags", "+faststart", output_filename
            ]
            subprocess.run(cmd_encode, check=True)

        duration = get_video_duration(output_filename)
        await status_msg.edit_text("📤 মার্জ শেষ! এখন আপলোড হচ্ছে...")
        
        video_caption = (
            f"🎬 **ফাইল নেম:** `{os.path.basename(output_filename)}`\n\n"
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
        if os.path.exists(list_filename): os.remove(list_filename)
        if os.path.exists(output_filename): os.remove(output_filename)
        if chat_id in user_data:
            for path in user_data[chat_id].get("files", []):
                if os.path.exists(path): os.remove(path)
            user_data[chat_id]["files"] = []
            user_data[chat_id]["total_size"] = 0

print("🚀 বটটি সচল করা হয়েছে!")
app.run()
