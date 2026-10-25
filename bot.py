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

app = Client("video_merger_v6", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# --- ফাংশন ১: ভিডিওর সময় বের করা ---
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

# --- ফাংশন ২: ভিডিওতে অডিও ট্র্যাক আছে কিনা চেক করা ---
def check_has_audio(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return bool(result.stdout.strip())
    except Exception:
        return False

# --- ফাংশন ৩: প্রোগ্রেস বার ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / (diff if diff > 0 else 1)
        
        progress = "[{0}{1}]".format(
            ''.join(["■" for _ in range(int(percentage / 10))]),
            ''.join(["□" for _ in range(10 - int(percentage / 10))])
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

# --- ৪. স্টার্ট কমান্ড ---
@app.on_message(filters.command("start"))
async def start(client, message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "files": [], 
        "total_size": 0, 
        "thumb": None, 
        "filename": f"merged_{chat_id}.mp4"
    }
    
    welcome_text = (
        "👋 **ভিডিও মার্জার বটে স্বাগতম!**\n\n"
        "🎬 **ব্যবহারবিধি:**\n"
        "১. আপনার ভিডিওগুলো একে একে পাঠান।\n"
        "২. সবগুলো পাঠানো শেষে **Done** লিখুন।\n"
        "৩. বট সব ভিডিওকে **একই রেজোলিউশন ও ফরম্যাটে নিখুঁতভাবে মার্জ** করে একটি মাত্র ভিডিও বানিয়ে দিবে (কোনো আটকে যাওয়া বা ল্যাগ হবে না)।\n\n"
        "⚙️ **অন্যান্য কমান্ড:**\n"
        "✏️ `/setname <নাম>` - ফাইনাল ভিডিওর নাম সেট করুন।\n"
        "❌ `/cancel` - প্রসেস বাতিল করুন।"
    )
    await message.reply_text(welcome_text)

# --- ৫. নাম সেট করা ---
@app.on_message(filters.command("setname"))
async def set_name(client, message):
    chat_id = message.chat.id
    if len(message.command) > 1:
        new_name = message.text.split(None, 1)[1]
        if not new_name.endswith(".mp4"): 
            new_name += ".mp4"
        if chat_id not in user_data: 
            user_data[chat_id] = {"files": [], "total_size": 0}
        user_data[chat_id]["filename"] = new_name
        await message.reply_text(f"✅ ফাইনাল ফাইলের নাম সেট করা হয়েছে: `{new_name}`")
    else:
        await message.reply_text("উদাহরণ: `/setname My_Movie.mp4`")

# --- ৬. বাতিল করা ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data:
        for path in user_data[chat_id].get("files", []):
            if os.path.exists(path): 
                os.remove(path)
        del user_data[chat_id]
        await message.reply_text("❌ প্রসেস বাতিল করা হয়েছে এবং ফাইলগুলো মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("কোনো প্রসেস রানিং নেই।")

# --- ৭. ভিডিও গ্রহণ হ্যান্ডলার ---
@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"files": [], "total_size": 0, "thumb": None, "filename": f"merged_{chat_id}.mp4"}

    if user_data[chat_id]["total_size"] >= MAX_LIMIT:
        await message.reply_text("⚠️ ২জিবি সাইজ পূর্ণ হয়ে গেছে! এখন **Done** লিখুন।")
        return

    status_msg = await message.reply_text("📥 ভিডিও ডাউনলোড শুরু হচ্ছে...", quote=True)
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
        f"✅ ভিডিও {len(user_data[chat_id]['files'])}টি যুক্ত হয়েছে।\n\n"
        f"📊 মোট সাইজ: {used_mb:.2f} MB (অবশিষ্ট: {remaining_mb:.2f} MB)\n\n"
        f"আরও পাঠাতে পারেন অথবা মার্জ করতে **Done** লিখুন।"
    )

# --- ৮. পারফেক্ট মার্জিং (Done কমান্ড) ---
@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos_done(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data or len(user_data[chat_id]["files"]) < 2:
        await message.reply_text("❌ মার্জ করতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    raw_files = user_data[chat_id]["files"]
    output_filename = user_data[chat_id].get("filename", f"merged_{chat_id}.mp4")

    status_msg = await message.reply_text(
        "⚙️ **সব ভিডিও একই রেজোলিউশন ও ফরম্যাটে রূপান্তর এবং মার্জ করা হচ্ছে...**\n"
        "*(ভিডিও সাইজ অনুযায়ী কিছুটা সময় লাগতে পারে, অপেক্ষা করুন)*"
    )

    try:
        # ১. FFmpeg কমান্ড তৈরি (স্কেলিং + কনক্যাট ফিল্টার)
        # রেজোলিউশন 1280x720 (720p) এ ফিক্সড করা হচ্ছে যাতে সব ডিসপ্লেতে স্মুথ চলে
        cmd = ["ffmpeg", "-y"]
        filter_complex = ""
        concat_inputs = ""

        for idx, file_path in enumerate(raw_files):
            cmd.extend(["-i", file_path])
            dur = get_video_duration(file_path)
            has_aud = check_has_audio(file_path)

            # ভিডিও স্কেল ও প্যাড (রেশিও ঠিক রেখে 720p ফিক্সড করা)
            filter_complex += (
                f"[{idx}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{idx}];"
            )

            # কোনো ভিডিওতে যদি অডিও না থাকে তবে সাইলেন্ট অডিও অ্যাড করবে যাতে মার্জ না ভাঙে
            if has_aud:
                filter_complex += f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{idx}];"
            else:
                filter_complex += f"aevalsrc=0:d={dur}[a{idx}];"

            concat_inputs += f"[v{idx}][a{idx}]"

        # সবগুলোকে জোড়া লাগানো
        filter_complex += f"{concat_inputs}concat=n={len(raw_files)}:v=1:a=1[outv][outa]"

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "veryfast",   # দ্রুত মার্জের জন্য
            "-crf", "24",            # ভালো কোয়ালিটি ও কম সাইজ
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_filename
        ])

        # সাবপ্রসেস রান করানো
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if not os.path.exists(output_filename) or os.path.getsize(output_filename) == 0:
            error_details = stderr.decode()[-300:] if stderr else "Unknown error"
            await status_msg.edit_text(f"❌ মার্জ করতে সমস্যা হয়েছে:\n`{error_details}`")
            return

        # ২. আপলোড প্রসেস
        await status_msg.edit_text("📤 সফলভাবে মার্জ হয়েছে! এখন আপলোড করা হচ্ছে...")
        duration = get_video_duration(output_filename)
        upload_start = time.time()

        await message.reply_video(
            video=output_filename,
            duration=duration,
            thumb=user_data[chat_id].get("thumb"),
            caption=(
                f"🎬 **ফাইনাল ভিডিও মার্জ সফল!**\n\n"
                f"📁 মোট ভিডিও: {len(raw_files)}টি\n"
                f"📐 ফিক্সড রেজোলিউশন: 720p (HD)\n"
                f"📊 সাইজ: {os.path.getsize(output_filename)/(1024*1024):.2f} MB"
            ),
            progress=progress_bar,
            progress_args=(status_msg, upload_start, "📤 আপলোড হচ্ছে...")
        )

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর দেখা দিয়েছে: {str(e)}")

    finally:
        # ফাইল ডিলিট ও মেমোরি ক্লিয়ার
        if chat_id in user_data:
            for path in user_data[chat_id].get("files", []):
                if os.path.exists(path): 
                    os.remove(path)
            user_data[chat_id]["files"] = []
            user_data[chat_id]["total_size"] = 0
            
        if os.path.exists(output_filename):
            os.remove(output_filename)

print("🚀 বট সম্পূর্ণভাবে প্রস্তুত!")
app.run()
