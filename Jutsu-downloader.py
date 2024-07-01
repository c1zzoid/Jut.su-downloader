import os
import requests
from bs4 import BeautifulSoup
from customtkinter import *
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import threading
import time
from tkinter import Menu
from pynput import keyboard

stop_download = False
current_episode_label = None
skip_fillers = False

def get_video_urls(page_url, resolution='480'):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(page_url, headers=headers)
    if response.status_code != 200:
        print(f"Ошибка: невозможно загрузить страницу: {page_url}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    video_urls = []

    title_tag = soup.find('h2', class_='header_video anime_padding_for_title_post_naruto')
    if title_tag and 'филлер' in title_tag.get('title', ''):
        print(f"Эпизод {page_url} является филлером. Пропускаем.")
        return []

    source_tags = soup.find_all('source', {'res': resolution})
    print(f"Найдено {len(source_tags)} исходные теги с разрешением {resolution} на {page_url}")

    for source in source_tags:
        video_url = source.get('src')
        if video_url:
            video_urls.append(video_url)
            print(f"Найдено видео: {video_url}")

    return video_urls

def download_video(video_url, output_directory, episode_number, series_name):
    global stop_download, current_episode_label

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(video_url, headers=headers, stream=True)
    if response.status_code == 200:
        video_filename = f"{series_name} {str(episode_number).zfill(3)}.mp4"
        output_path = os.path.join(output_directory, video_filename)

        if os.path.exists(output_path):
            print(f"Файл {video_filename} уже существует. Пропуск загрузки.")
            return

        total_length = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if stop_download:
                    f.close()
                    os.remove(output_path)
                    print(f'Загрузка отменена и неполный файл удален: {video_filename}')
                    return
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed_time = time.time() - start_time
                    speed = downloaded / elapsed_time / (1024 * 1024) if elapsed_time > 0 else 0  # MB/s
                    percentage = (downloaded / total_length) * 100
                    current_episode_label.configure(text=f"Скачивается: {series_name} {str(episode_number).zfill(3)} ({percentage:.2f}%) - {speed:.2f} MB/s")
                    root.update_idletasks()

        print(f'Скачено: {video_filename}')
    else:
        print(f"Ошибка: невозможно скачать видео с {video_url}")

def get_directory():
    directory = filedialog.askdirectory(title="Выберите директорию для сохранения видео")
    if directory:
        directory_var.set(directory)
        folder_name = os.path.basename(directory)
        truncated_folder_name = (folder_name[:30] + '...') if len(folder_name) > 30 else folder_name
        selected_directory_label.configure(text=f"Папка: {truncated_folder_name}")
        directory_button.configure(fg_color="darkolivegreen")
    return directory

def create_context_menu(widget):
    menu = Menu(widget, tearoff=0)
    menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
    widget.bind("<Button-3>", lambda event: menu.tk_popup(event.x_root, event.y_root))

def start_download(url, start_episode, end_episode, output_directory, resolution):
    global stop_download, current_episode_label, skip_fillers

    stop_download = False

    if "episode-" in url:
        base_url = url.rsplit('/', 1)[0]
    elif "season-" in url:
        base_url = url.rstrip('/')
    else:
        season = CTkInputDialog(text="Введите номер сезона (например, 1, 2, 3 и т.д.):", title="Введите сезон").get_input()
        if season:
            url = url.rstrip('/') + f"/season-{season}/"
            base_url = url.rstrip('/')
        else:
            messagebox.showwarning("Ошибка ввода", "Сезон не указан. Пожалуйста, введите номер сезона.")
            return

    series_name = url.split('/')[3].replace('-', ' ')
    if "season-" in url:
        series_name += " " + url.split('/')[4].replace('-', ' ')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for episode in range(start_episode, end_episode + 1):
        page_url = f'{base_url}/episode-{episode}.html'
        print(f"Получаем видео из {page_url}")
        current_episode_label.configure(text=f"Скачивается: {series_name} {str(episode).zfill(3)} (0%)")
        root.update_idletasks()
        video_urls = get_video_urls(page_url, resolution)
        
        if not video_urls:
            print("No video URLs found.")
            continue

        if any(os.path.exists(os.path.join(output_directory, f"{series_name} {str(episode).zfill(3)}.mp4")) for _ in video_urls):
            print(f"Эпизод {series_name} {str(episode).zfill(3)} уже скачан. Пропускаем.")
            continue

        for url in video_urls:
            print(f"Качаем: {url}")
            download_video(url, output_directory, episode, series_name)
            if stop_download:
                return

    messagebox.showinfo("Загрузка завершена", "Все видео были успешно загружены!")

def on_start_download():
    url = url_entry.get()
    try:
        start_episode = int(start_episode_entry.get())
        end_episode = int(end_episode_entry.get())
    except ValueError:
        messagebox.showwarning("Ошибка ввода", "Номер эпизода должен быть числом.")
        return

    output_directory = directory_var.get()
    resolution = resolution_var.get()

    if not url or not start_episode or not end_episode or not output_directory:
        messagebox.showwarning("Ошибка ввода", "Пожалуйста, заполните все поля.")
        return

    download_thread = threading.Thread(target=start_download, args=(url, start_episode, end_episode, output_directory, resolution))
    download_thread.start()

def on_stop_download():
    global stop_download
    stop_download = True

def on_paste(key):
    root.focus_get().insert(INSERT, root.clipboard_get())

def on_toggle_skip_fillers():
    global skip_fillers
    skip_fillers = not skip_fillers
    skip_fillers_button.configure(text="Не качать филлеры" if skip_fillers else "Качать все")

listener = keyboard.GlobalHotKeys({
    '<ctrl>+v': on_paste,
    '<ctrl>+V': on_paste
})
listener.start()

set_appearance_mode("dark")
set_default_color_theme("blue")

root = CTk()
root.title("Jutsu Downloader")
root.geometry("700x450")

frame = CTkFrame(root)
frame.pack(pady=20, padx=20, fill="both", expand=True)

url_label = CTkLabel(frame, text="Введите URL страницы с аниме:")
url_label.grid(row=0, column=0, pady=10, padx=10, sticky='e')
url_entry = CTkEntry(frame, width=300)
url_entry.grid(row=0, column=1, pady=10, padx=10)
create_context_menu(url_entry)

start_episode_label = CTkLabel(frame, text="Введите начальный номер эпизода:")
start_episode_label.grid(row=1, column=0, pady=10, padx=10, sticky='e')
start_episode_entry = CTkEntry(frame, width=50)
start_episode_entry.grid(row=1, column=1, pady=10, padx=10, sticky='w')
create_context_menu(start_episode_entry)

end_episode_label = CTkLabel(frame, text="Введите конечный номер эпизода:")
end_episode_label.grid(row=2, column=0, pady=10, padx=10, sticky='e')
end_episode_entry = CTkEntry(frame, width=50)
end_episode_entry.grid(row=2, column=1, pady=10, padx=10, sticky='w')
create_context_menu(end_episode_entry)

directory_label = CTkLabel(frame, text="Выберите директорию для сохранения видео:")
directory_label.grid(row=3, column=0, pady=10, padx=10, sticky='e')
directory_var = StringVar()
directory_button = CTkButton(frame, text="Выбрать директорию", command=get_directory)
directory_button.grid(row=3, column=1, pady=10, padx=10, sticky='w')

selected_directory_label = CTkLabel(frame, text="Папка: Не выбрана", width=30)
selected_directory_label.grid(row=3, column=1, pady=10, padx=(200, 0), sticky='w')

resolution_label = CTkLabel(frame, text="Выберите качество видео:")
resolution_label.grid(row=4, column=0, pady=10, padx=10, sticky='e')
resolution_var = StringVar(value="480")
resolutions = ["360", "480", "720", "1080"]
resolution_menu = CTkOptionMenu(frame, variable=resolution_var, values=resolutions)
resolution_menu.grid(row=4, column=1, pady=10, padx=10, sticky='w')

skip_fillers_button = CTkButton(frame, text="Качать все", command=on_toggle_skip_fillers)
skip_fillers_button.grid(row=5, column=0, pady=20, padx=10, sticky='e')

start_button = CTkButton(frame, text="Начать загрузку", command=on_start_download)
start_button.grid(row=5, column=1, pady=20, padx=10, sticky='w')

stop_button = CTkButton(frame, text="Остановить загрузку", command=on_stop_download)
stop_button.grid(row=6, column=0, pady=20, padx=10, sticky='w')

current_episode_label = CTkLabel(frame, text="")
current_episode_label.grid(row=7, column=0, columnspan=2)

root.mainloop()
