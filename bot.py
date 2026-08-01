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

# --- ফাংশন ২: ভিডিওর রেজোলিউশন বের করা ---
def get_video_resolution(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        res = result.stdout.strip()
        return res if res else "Unknown"
    except Exception:
        return "Unknown"

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

# --- ৪. স্টার্ট কমান্ড ---
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
        "👋 **ইনস্ট্যান্ট সুপার-ফাস্ট মার্জার বটে স্বাগতম!**\n\n"
        "🎬 **ইনস্ট্যান্ট গ্রুপ মার্জ মোড:**\n"
        "১. আপনার ভিডিওগুলো পাঠান।\n"
        "২. পাঠানো শেষ হলে **Done** লিখুন।\n"
        "৩. বট কোনো রেন্ডারিং ছাড়াই **অটোমেটিক ফরম্যাট অনুযায়ী ভাগ করে ২ সেকেন্ডে মার্জ করে দেবে!**\n\n"
        "⚙️ **অন্যান্য কমান্ড:**\n"
        "✏️ **/setname** - ফাইলের নাম সেট করুন।\n"
        "❌ **/cancel** - প্রসেস বাতিল করুন।"
    )
    await message.reply_text(welcome_text)

# --- ৫. নাম সেট করা ---
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

# --- ৬. বাতিল করা ---
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

# --- ৭. ভিডিও হ্যান্ডলার ---
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

# --- ৮. ইনস্ট্যান্ট গ্রুপ মার্জিং (Done কমান্ড) ---
@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos_done(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data or len(user_data[chat_id]["files"]) < 2:
        await message.reply_text("❌ মার্জ করতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("⚡ ফরম্যাট অনুযায়ী গ্রুপে ভাগ করা হচ্ছে...")
    raw_files = user_data[chat_id]["files"]

    try:
        # ১. রেজোলিউশন অনুযায়ী গ্রুপে ভাগ করা
        format_groups = {}
        for file_path in raw_files:
            res = get_video_resolution(file_path)
            if res not in format_groups:
                format_groups[res] = []
            format_groups[res].append(file_path)

        total_groups = len(format_groups)
        await status_msg.edit_text(f"📊 **মোট ভিডিও:** {len(raw_files)}টি\n🎯 **ফরম্যাট গ্রুপ পাওয়া গেছে:** {total_groups}টি\n\n⚡ জিরো-রেন্ডারিং মার্জিং শুরু হচ্ছে...")

        # ২. প্রতিটা গ্রুপের ভিডিও ১ সেকেন্ডে (-c copy) মার্জ করে পাঠানো
        group_idx = 1
        for res, files_in_group in format_groups.items():
            
            # যদি নির্দিষ্ট ফরম্যাটের ১টাই ভিডিও থাকে, তবে জোড়া লাগানোর দরকার নাই
            if len(files_in_group) == 1:
                await message.reply_video(
                    video=files_in_group[0],
                    caption=f"📁 **গ্রুপ {group_idx} ({res}):** ১টি ফাইল (অন্যগুলোর সাথে সাইজ না মিলায় আলাদা দেওয়া হলো)"
                )
                group_idx += 1
                continue

            # মার্জিং শুরু (ইনস্ট্যান্ট কপি)
            list_filename = f"list_{chat_id}_{group_idx}.txt"
            custom_name = user_data[chat_id].get("filename", f"merged_{chat_id}.mp4")
            output_filename = f"Group_{group_idx}_{res}_{custom_name}"

            with open(list_filename, "w") as f:
                for path in files_in_group:
                    f.write(f"file '{os.path.abspath(path)}'\n")

            fast_concat_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_filename,
                "-c", "copy", "-movflags", "+faststart", output_filename
            ]

            proc = await asyncio.create_subprocess_exec(*fast_concat_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                duration = get_video_duration(output_filename)
                
                upload_start = time.time()
                await message.reply_video(
                    video=output_filename,
                    duration=duration,
                    thumb=user_data[chat_id].get("thumb"),
                    caption=(
                        f"🎬 **মার্জ করা ভিডিও (গ্রুপ {group_idx}):**\n\n"
                        f"📐 **রেজোলিউশন:** {res}\n"
                        f"✅ **একত্রিত ভিডিও:** {len(files_in_group)}টি\n"
                        f"📊 **সাইজ:** {os.path.getsize(output_filename)/(1024*1024):.2f} MB\n"
                        f"⚡ **প্রসেস স্পিড:** ইনস্ট্যান্ট (জিরো রেন্ডারিং)"
                    )
                )

            # গ্রুপ ক্লিনআপ
            if os.path.exists(list_filename): os.remove(list_filename)
            if os.path.exists(output_filename): os.remove(output_filename)
            group_idx += 1

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")
    
    finally:
        if chat_id in user_data:
            for path in user_data[chat_id].get("files", []):
                if os.path.exists(path): os.remove(path)
            user_data[chat_id]["files"] = []
            user_data[chat_id]["total_size"] = 0

print("🚀 ইনস্ট্যান্ট গ্রুপ ফাস্ট মার্জার পুরোপুরি সচল!")
app.run()
