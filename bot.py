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
BOT_TOKEN = "8710959010:AAF1YxwB7iwTXj0kU302tPD06nlx4wbzTx0"
MAX_LIMIT = 2000 * 1024 * 1024  # ২জিবি লিমিট (বাইটসে)

app = Client("video_merger_v3", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- ফাংশন ১: ভিডিওর সময় (ডিউরেশন) বের করা ---
def get_video_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        val = float(result.stdout.strip())
        return max(1, int(val))
    except Exception:
        return 10  # ব্যাকআপ ১০ সেকেন্ড

# --- ফাংশন ১.১: অডিও ট্র্যাক আছে কিনা তা দেখা ---
def has_audio_stream(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_streams", "-select_streams", "a",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except Exception:
        return False

# --- ফাংশন ২: প্রোগ্রেস বার ---
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

# --- ফাংশন ৩: প্রসেসিং হার্টবিট ---
async def edit_heartbeat(status_msg, start_time, title="ভিডিও প্রসেসিং চলছে..."):
    icons = ["⚙️", "🪄", "⏳", "⌛"]
    idx = 0
    try:
        while True:
            elapsed = round(time.time() - start_time)
            icon = icons[idx % 4]
            text = (f"{icon} **{title}**\n\n"
                    f"⏱ অতিবাহিত সময়: {elapsed} সেকেন্ড\n"
                    f"🚀 বিভিন্ন ফরম্যাটের ভিডিও স্মুথ করতে রেন্ডারিং হচ্ছে।\n"
                    f"⚠️ ৫১২এমবি র‍্যাম অপটিমাইজেশন মোড সক্রিয়।")
            await status_msg.edit_text(text)
            idx += 1
            await asyncio.sleep(8)
    except Exception:
        pass

# --- ৪. স্টার্ট কমান্ড ---
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

# --- ৫. মিউজিক সেট করা ---
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

# --- ৬. ফেসবুক এডিট মোড ---
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
    
    if user_data[chat_id].get("thumb") and os.path.exists(user_data[chat_id]["thumb"]):
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

# --- ১০. ভিডিও হ্যান্ডলার ---
@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "state": "none", "filename": f"final_{chat_id}.mp4"}

    # ক) ফেসবুক এডিট মোড
    if user_data[chat_id].get("state") == "waiting_for_edit":
        user_data[chat_id]["state"] = "none"
        status_msg = await message.reply_text("📥 এডিটিংয়ের জন্য ভিডিও ডাউনলোড হচ্ছে...", quote=True)
        start_time = time.time()
        
        v_path = await message.download(
            progress=progress_bar, 
            progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
        )
        
        edit_start_time = time.time()
        heartbeat_task = asyncio.create_task(edit_heartbeat(status_msg, edit_start_time, "ফেসবুক ভিডিও টিউন হচ্ছে..."))
        
        out_v = f"fb_edit_{chat_id}_{time.time()}.mp4"
        bgm = user_data[chat_id]["music"]
        
        # অডিও থাকলে মিক্স হবে, না থাকলে শুধু BGM ডাইরেক্ট বসবে
        if has_audio_stream(v_path):
            filter_str = (
                "[0:v]scale=-2:720,eq=saturation=1.4:contrast=1.2:brightness=0.03[v];"
                "[0:a]volume=1.8[a1];"
                "[1:a]volume=0.03[a2];"
                "[a1][a2]amix=inputs=2:duration=first[a]"
            )
        else:
            filter_str = (
                "[0:v]scale=-2:720,eq=saturation=1.4:contrast=1.2:brightness=0.03[v];"
                "[1:a]volume=1.0[a]"
            )
        
        cmd = [
            "ffmpeg", "-y", "-i", v_path, "-i", bgm,
            "-filter_complex", filter_str,
            "-map", "[v]", "-map", "[a]", 
            "-c:v", "libx264", 
            "-preset", "ultrafast",  
            "-crf", "28",            
            "-threads", "0",         
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
            caption="🎬 **আপনার ফেসবুক শর্টস ভিডিও রেডি!**",
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

    used_mb = user_data[chat_id]["total_size"] / (1024 * 1024)
    remaining_mb = (MAX_LIMIT - user_data[chat_id]["total_size"]) / (1024 * 1024)

    await status_msg.edit_text(
        f"✅ ভিডিও {len(user_data[chat_id]['files'])} যুক্ত হয়েছে।\n\n"
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

    status_msg = await message.reply_text("⚙️ ভিডিওগুলোকে স্মুথ এবং স্ট্যান্ডার্ড ফরম্যাটে মার্জ করা হচ্ছে...")
    output_filename = user_data[chat_id].get("filename", f"merged_{chat_id}.mp4")
    files_list = user_data[chat_id]["files"]
    num_files = len(files_list)

    try:
        start_time = time.time()
        heartbeat_task = asyncio.create_task(edit_heartbeat(status_msg, start_time, "ভিডিও জোড়া লাগানো হচ্ছে..."))

        cmd = ["ffmpeg", "-y"]
        for file_path in files_list:
            cmd.extend(["-i", file_path])

        filter_complex = ""
        for i, file_path in enumerate(files_list):
            v_dur = get_video_duration(file_path)
            
            filter_complex += (
                f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:(1280-iw)/2:(720-ih)/2,setsar=1,fps=30[v{i}]; "
            )
            
            # অডিও থাকলে নরমাল স্টেরিও হবে, না থাকলে নির্ধারিত ডিউরেশনের সাইলেন্ট অডিও তৈরি হবে
            if has_audio_stream(file_path):
                filter_complex += f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]; "
            else:
                filter_complex += f"anullsrc=r=44100:cl=stereo,atrim=end={v_dur}[a{i}]; "

        for i in range(num_files):
            filter_complex += f"[v{i}][a{i}]"
        
        filter_complex += f"concat=n={num_files}:v=1:a=1[outv][outa]"

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "ultrafast",  
            "-crf", "28",            
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_filename
        ])

        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()

        heartbeat_task.cancel()

        # ০ বাইট এরর হ্যান্ডলিং চেক
        if process.returncode != 0 or not os.path.exists(output_filename) or os.path.getsize(output_filename) == 0:
            err_msg = stderr.decode().strip()
            raise Exception(f"FFmpeg প্রসেসিং ফেল করেছে: {err_msg[-200:] if err_msg else 'খালি ফাইল তৈরি হয়েছে'}")

        duration = get_video_duration(output_filename)
        await status_msg.edit_text("📤 জোড়া লাগানো সম্পন্ন! এখন আপলোড হচ্ছে...")
        
        video_caption = (
            f"🎬 **ফাইল নেম:** `{output_filename}`\n\n"
            f"✅ **মোট ফাইল:** {num_files}\n"
            f"📊 **সাইজ:** {os.path.getsize(output_filename)/(1024*1024):.2f} MB\n"
            f"⏳ **সময়:** {time.strftime('%H:%M:%S', time.gmtime(duration))}\n"
            f"✨ **কোয়ালিটি:** স্মুথ প্লেব্যাক ও ৭২০পি ফিক্সড।"
        )

        upload_start = time.time()
        await message.reply_video(
            video=output_filename,
            duration=duration,
            thumb=user_data[chat_id].get("thumb"),
            caption=video_caption,
            progress=progress_bar,
            progress_args=(status_msg, upload_start, "📤 আপলোড হচ্ছে...")
        )
        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")
    
    finally:
        if os.path.exists(output_filename): 
            os.remove(output_filename)
        if chat_id in user_data:
            for path in user_data[chat_id].get("files", []):
                if os.path.exists(path): 
                    os.remove(path)
            user_data[chat_id]["files"] = []
            user_data[chat_id]["total_size"] = 0

print("🚀 ফিক্সড সাইলেন্ট ট্রিম ট্র্যাকিং সহ বট প্রস্তুত!")
app.run()
