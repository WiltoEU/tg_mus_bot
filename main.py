import os
import asyncio
import threading
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL
import imageio_ffmpeg
from flask import Flask

BOT_TOKEN = "8590062181:AAGjBTW98YtZbhVsyfYW4vzew-2fq03mczQ"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Получаем путь к встроенному FFmpeg автоматически
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()


# --- ФУНКЦИИ ПОИСКА И СКАЧИВАНИЯ ---

def search_tracks(query: str, limit: int = 8):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'ffmpeg_location': ffmpeg_path,
    }
    results = []
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        for entry in info.get('entries', []):
            duration = entry.get('duration', 0)
            minutes, seconds = divmod(duration, 60)
            results.append({
                'id': entry.get('id'),
                'title': entry.get('title'),
                'uploader': entry.get('uploader', 'Unknown'),
                'duration_str': f"{minutes}:{seconds:02d}",
            })
    return results


def download_audio(video_url: str, output_path: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path,
        'quiet': True,
        'ffmpeg_location': ffmpeg_path,
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])


# --- ОБРАБОТЧИКИ TELEGRAM БОТА ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Напиши название песни или исполнителя, и я найду MP3-файл.")


@dp.message(F.text)
async def handle_search(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🔎 Ищу аудиозаписи по запросу «{query}»...")

    results = await asyncio.to_thread(search_tracks, query)

    if not results:
        await status_msg.edit_text("Ничего не найдено. Попробуйте изменить запрос.")
        return

    keyboard_buttons = []
    for track in results:
        btn_text = f"{track['duration_str']} {track['title']}"
        if len(btn_text) > 60:
            btn_text = btn_text[:57] + "..."
        keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"dl:{track['id']}")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await status_msg.edit_text(f"Аудиозаписи по запросу «{query}»:", reply_markup=markup)


@dp.callback_query(F.data.startswith("dl:"))
async def handle_download(callback: types.CallbackQuery):
    video_id = callback.data.split(":")[1]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    await callback.answer("Скачиваю аудио...")
    file_prefix = f"song_{callback.from_user.id}_{video_id}"
    output_tmpl = f"{file_prefix}.%(ext)s"
    final_file = f"{file_prefix}.mp3"

    try:
        await asyncio.to_thread(download_audio, video_url, output_tmpl)
        audio_file = types.FSInputFile(final_file)
        await callback.message.answer_audio(audio=audio_file)
    except Exception as e:
        await callback.message.answer("❌ Произошла ошибка при скачивании трека.")
        print(f"Ошибка: {e}")
    finally:
        if os.path.exists(final_file):
            os.remove(final_file)


# --- FLASK СЕРВЕР (ДЛЯ ЗАЩИТЫ ОТ ЗАСЫПАНИЯ) ---

app = Flask('')


@app.route('/')
def home():
    return "Bot is active and running!"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()


# --- ЗАПУСК ВСЕГО ВМЕСТЕ ---

async def main():
    keep_alive()  # Запускаем веб-сервер в фоне
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())