FROM python:3.9-slim-buster

# FFmpeg এবং প্রয়োজনীয় টুলস ইনস্টল
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY . .

# লাইব্রেরি ইনস্টল
RUN pip install --no-cache-dir -r requirements.txt

# ডাউনলোড ফোল্ডার তৈরি
RUN mkdir downloads

CMD ["python", "bot.py"]
