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

app = Client("video_merger_v5", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- ফাংশন ১: ভিডিওর সময় বের করা ---
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
        return 10

# --- ফাংশন ২: ভিডিওর রেজোলিউশন (সাইজ) বের করা ---
def get_video_resolution(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip() # যেমন: "1280x720" বা "1920x1080"
    except Exception:
        return "1280x720"

# --- ফাংশন ৩: প্রোগ্রেস বার ---
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

# --- ফাংশন ৪: প্রসেসিং হার্টবিট ---
async def edit_heartbeat(status_msg, start_time, title="স্মার্ট প্রসেসিং চলছে..."):
    icons = ["⚡", "🧠", "⏳", "⌛"]
    idx = 0
    try:
        while True:
            elapsed = round(time.time() - start_time)
            icon = icons[idx % 4]
            text = (f"{icon} **{title}**\n\n"
                    f"⏱ সময় অতিবাহিত: {elapsed} সেকেন্ড\n"
                    f"🧠 শুধু ভিন্ন ফরম্যাটের ভিডিওটি অ্যাডজাস্ট করা হচ্ছে...")
            await status_msg.edit_text(text)
            idx += 1
            await asyncio.sleep(5)
    except Exception:
        pass

# --- ৫. স্টার্ট কমান্ড ---
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
        "👋 **স্মার্ট ভিডিও মার্জার বটে স্বাগতম!**\n\n"
        "🎬 **ভিডিও জোড়া লাগানো (Merge Mode):**\n"
        "সরাসরি ভিডিওগুলো পাঠান। সব পাঠানো শেষ হলে **Done** লিখুন।\n\n"
        "⚙️ **অন্যান্য কমান্ড:**\n"
        "✏️ **/setname** - ফাইলের নাম সেট করুন।\n"
        "❌ **/cancel** - প্রসেস বাতিল করুন।"
    )
    await message.reply_text(welcome_text)

# --- ৬. নাম সেট করা ---
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

# --- ৭. বাতিল করা ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        for path in user_data[chat_id].get("files", []):
            if os.path.exists(path): os.remove(path)
        del user_data[chat_id]
        await message.reply_text("❌ সব বাতিল এবং ফাইল মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("কোনো প্রসেস রানিং নেই।")

# --- ৮. ভিডিও হ্যান্ডলার ---
@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "filename": f"final_{chat_id}.mp4"}

    if user_data[chat_id]["total_size"] >= MAX_LIMIT:
        await message.reply_text("⚠️ লিমিট শেষ! আপনি ২জিবি পূর্ণ করে ফেলেছেন। **Done** লিখুন।")
        return

    status_msg = await message.reply_text("📥 ভিডিও যুক্ত হচ্ছে...", quote=True)
    start_time = time.time()
    
    file_path = await message.download(
        progress=progress_bar, progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
    )

    f_size = os.path.getsize(file_path)
    user_data[chat_id]["files"].append(file_path)
    user_data[chat_id]["total_size"] += f_size

    used_mb = user_data[chat_id]["total_size"] / (1024 * 1024)
    remaining_mb = (MAX_LIMIT - user_data[chat_id]["total_size"]) / (1024 * 1024)

    await status_msg.edit_text(
        f"✅ ভিডিও {len(user_data[chat_id]['files'])} যুক্ত হয়েছে।\n\n"
        f"📊 মোট সাইজ: {used_mb:.2f} MB (খালি: {remaining_mb:.2f} MB)\n\n"
        f"পরেরটি পাঠান অথবা **Done** লিখুন।"
    )

# --- ৯. স্মার্ট সিলেক্টিভ মার্জিং (Done কমান্ড) ---
@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos_done(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data or len(user_data[chat_id]["files"]) < 2:
        await message.reply_text("❌ মার্জ করতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("🔍 ভিডিওগুলোর সাইজ পরীক্ষা করা হচ্ছে...")
    output_filename = user_data[chat_id].get("filename", f"merged_{chat_id}.mp4")
    raw_files = user_data[chat_id]["files"]
    processed_files = []
    temp_converted_files = [] # ক্লিনআপ করার জন্য

    try:
        start_time = time.time()
        heartbeat_task = asyncio.create_task(edit_heartbeat(status_msg, start_time, "স্মার্ট ফরম্যাট চেকিং..."))

        # ১. প্রথম ভিডিওটিকে রেফারেন্স সাইজ হিসেবে ধরা
        target_res = get_video_resolution(raw_files[0])
        target_w, target_h = target_res.split("x")

        # ২. লুপ চালিয়ে শুধু ভিন্ন সাইজের ভিডিওগুলোকে কনভার্ট করা
        for idx, file_path in enumerate(raw_files):
            current_res = get_video_resolution(file_path)
            
            if current_res == target_res:
                # সাইজ মিলে গেছে! প্রসেস করার দরকার নাই (০ সেকেন্ড)
                processed_files.append(file_path)
            else:
                # সাইজ মিলে নাই! কেবল এই একটি ভিডিওকে প্রথমটার মাপে কনভার্ট করো
                temp_out = f"downloads/temp_{chat_id}_{idx}.mp4"
                temp_converted_files.append(temp_out)
                
                cmd_convert = [
                    "ffmpeg", "-y", "-i", file_path,
                    "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    temp_out
                ]
                proc = await asyncio.create_subprocess_exec(*cmd_convert, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
                processed_files.append(temp_out)

        # ৩. সব ভিডিও এখন হুবহু একই ফরম্যাটে চলে এসেছে! এখন ফাস্ট কপি দিয়ে ২ সেকেন্ডে জোড়া দেওয়া
        list_filename = f"list_{chat_id}.txt"
        with open(list_filename, "w") as f:
            for path in processed_files:
                f.write(f"file '{os.path.abspath(path)}'\n")

        fast_concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_filename,
            "-c", "copy", "-movflags", "+faststart", output_filename
        ]

        proc_concat = await asyncio.create_subprocess_exec(*fast_concat_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc_concat.communicate()

        heartbeat_task.cancel()

        if not os.path.exists(output_filename) or os.path.getsize(output_filename) == 0:
            raise Exception("মার্জ করা সম্ভব হয়নি। ফাইলগুলো সচল আছে কিনা চেক করুন।")

        duration = get_video_duration(output_filename)
        await status_msg.edit_text("📤 জোড়া লাগানো শেষ! এখন আপলোড হচ্ছে...")
        
        video_caption = (
            f"🎬 **ফাইল নেম:** `{output_filename}`\n"
            f"✅ **মোট ফাইল:** {len(raw_files)}\n"
            f"📊 **সাইজ:** {os.path.getsize(output_filename)/(1024*1024):.2f} MB\n"
            f"⏳ **সময়:** {time.strftime('%H:%M:%S', time.gmtime(duration))}\n"
            f"⚡ **টেকনোলজি:** স্মার্ট সিলেক্টিভ মার্জার।"
        )

        upload_start = time.time()
        await message.reply_video(
            video=output_filename, duration=duration,
            thumb=user_data[chat_id].get("thumb"), caption=video_caption,
            progress=progress_bar, progress_args=(status_msg, upload_start, "📤 আপলোড হচ্ছে...")
        )
        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")
    
    finally:
        # সব টেম্পোরারি ফাইল ক্লিনআপ
        if 'list_filename' in locals() and os.path.exists(list_filename): 
            os.remove(list_filename)
        if os.path.exists(output_filename): 
            os.remove(output_filename)
            
        for temp_f in temp_converted_files:
            if os.path.exists(temp_f): 
                os.remove(temp_f)
                
        if chat_id in user_data:
            for path in user_data[chat_id].get("files", []):
                if os.path.exists(path): 
                    os.remove(path)
            user_data[chat_id]["files"] = []
            user_data[chat_id]["total_size"] = 0

print("🧠 স্মার্ট সিলেক্টিভ মার্জার সক্রিয়!")
app.run()
