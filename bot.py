import os
import time
import subprocess
import asyncio
from pyrogram import Client, filters

# FFmpeg অটো-সেটআপ (সার্ভারে এরর বন্ধ করার জন্য)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# আপনার ভেরিয়েবলগুলো (ফিক্সড)
API_ID = "19234664"
API_HASH = "29c2f3b3d115cf1b0231d816deb271f5"
BOT_TOKEN = "8710959010:AAHfutLem56XMMvNN9GG6n-xwJUiKYA2J7s"

app = Client("video_merger", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ইউজার ডাটা ডিকশনারি
user_data = {}

# ডাউনলোড ফোল্ডার তৈরি
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ভিডিওর সঠিক সময় (মিনিট/সেকেন্ড) বের করার ফাংশন
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

# প্রোগ্রেস বার ফাংশন
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

@app.on_message(filters.command("start"))
async def start(client, message):
    user_data[message.chat.id] = []
    await message.reply_text(
        "👋 স্বাগতম! আমি আপনার ভিডিওগুলো সিরিয়াল অনুযায়ী নিখুঁতভাবে জোড়া লাগিয়ে দেব।\n\n"
        "১. একে একে আপনার ভিডিওগুলো পাঠান (এপিসোড ১, ২, ৩...)।\n"
        "২. সব পাঠানো শেষ হলে **Done** লিখে মেসেজ দিন।\n"
        "৩. ভুল ফাইল পাঠালে তা বাতিল করতে **/cancel** লিখুন।"
    )

# --- ক্যানসেল কমান্ড ---
@app.on_message(filters.command("cancel"))
async def cancel_process(client, message):
    chat_id = message.chat.id
    if chat_id in user_data and user_data[chat_id]:
        for path in user_data[chat_id]:
            if os.path.exists(path):
                os.remove(path)
        user_data[chat_id] = []
        await message.reply_text("❌ আপনার বর্তমান প্রসেসটি বাতিল করা হয়েছে এবং সব ভিডিও মুছে ফেলা হয়েছে। আপনি নতুন করে শুরু করতে পারেন।")
    else:
        await message.reply_text("আপনার কোনো প্রসেস বর্তমানে রানিং নেই।")

@app.on_message(filters.video)
async def handle_video(client, message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = []

    status_msg = await message.reply_text("📥 ভিডিওটি ডাউনলোড হচ্ছে...", quote=True)
    start_time = time.time()

    # ইউজারের জন্য আলাদা সাব-ফোল্ডার
    user_dir = f"downloads/{chat_id}"
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    # ডাউনলোড করা
    file_path = await message.download(
        file_name=f"{user_dir}/{time.time()}.mp4",
        progress=progress_bar,
        progress_args=(status_msg, start_time, "📥 ডাউনলোড হচ্ছে...")
    )

    user_data[chat_id].append(file_path)
    await status_msg.edit_text(f"✅ এপিসোড {len(user_data[chat_id])} সফলভাবে যুক্ত হয়েছে।\nপরেরটি পাঠান অথবা **Done** লিখুন।\n\n(ভুল হলে **/cancel** লিখে সব মুছুন)")

@app.on_message(filters.text & filters.regex("(?i)^done$"))
async def merge_videos(client, message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or len(user_data[chat_id]) < 2:
        await message.reply_text("❌ ভিডিও জোড়া লাগাতে কমপক্ষে ২টি ভিডিও পাঠাতে হবে!")
        return

    status_msg = await message.reply_text("⚙️ ভিডিওগুলো প্রসেস করা হচ্ছে... দয়া করে অপেক্ষা করুন।")
    
    output_filename = f"final_video_{chat_id}.mp4"
    list_filename = f"list_{chat_id}.txt"

    try:
        # FFmpeg লিস্ট ফাইল তৈরি
        with open(list_filename, "w") as f:
            for path in user_data[chat_id]:
                f.write(f"file '{os.path.abspath(path)}'\n")

        # ধাপ ১: ভিডিওগুলো মার্জ করা (Fast Copy Mode + Faststart)
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_filename, "-c", "copy", "-movflags", "+faststart", output_filename
        ]
        
        merge_process = subprocess.run(cmd, capture_output=True, text=True)

        # যদি ভিডিও ফরম্যাট ভিন্ন হওয়ার কারণে 'copy' মোড ফেল করে
        if merge_process.returncode != 0:
            await status_msg.edit_text("⚠️ ভিডিওর ফরম্যাট ভিন্ন, তাই এনকোডিং শুরু হচ্ছে (এতে একটু বেশি সময় লাগতে পারে)...")
            cmd_encode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_filename, "-movflags", "+faststart", output_filename
            ]
            subprocess.run(cmd_encode, check=True)

        # ধাপ ২: ভিডিওর সঠিক দৈর্ঘ্য (সময়) বের করা
        duration = get_video_duration(output_filename)

        # ধাপ ৩: আপলোড করা
        await status_msg.edit_text("📤 ভিডিও তৈরি! এখন আপলোড হচ্ছে...")
        start_time = time.time()
        
        await message.reply_video(
            video=output_filename,
            duration=duration,  # এটি ভিডিওর মিনিট/সেকেন্ড ফিক্স করবে
            caption=f"🎬 **আপনার ভিডিওটি তৈরি!**\n\n✅ মোট এপিসোড: {len(user_data[chat_id])}\n📊 সময়: {time.strftime('%H:%M:%S', time.gmtime(duration))}",
            progress=progress_bar,
            progress_args=(status_msg, start_time, "📤 আপলোড হচ্ছে...")
        )

        await status_msg.delete()

    except Exception as e:
        await message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")
    
    finally:
        # সব টেম্পোরারি ফাইল মুছে ফেলা
        if os.path.exists(list_filename): os.remove(list_filename)
        if os.path.exists(output_filename): os.remove(output_filename)
        if chat_id in user_data:
            for path in user_data[chat_id]:
                if os.path.exists(path): os.remove(path)
            user_data[chat_id] = []

print("🔥 বটটি সফলভাবে চালু হয়েছে এবং কাজ করার জন্য প্রস্তুত!")
app.run()
