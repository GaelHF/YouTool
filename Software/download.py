import tkinter as tk
import requests
from pytube import YouTube

video_directory = "../Videos"
thumbnail_directory = "../Thumbnails"

def download_youtube_video():
    url = link_input.get()
    if url:
        try:
            yt = YouTube(url)
            title = yt.title
            yt.streams.filter(progressive=True, file_extension='mp4')
            yt.streams.get_highest_resolution().download(output_path=video_directory)
            log_message.set("Successfully downloaded: " + str(title))
            print("Successfully downloaded: " + str(title))
        except Exception as e:
            log_message.set(f"An error occurred: {e}")

def download_youtube_thumbnail():
    url = link_input.get()
    if url:
        try:
            yt = YouTube(url)
            title = yt.title
            img_url = yt.thumbnail_url
            content =  requests.get(img_url).content
            minia = open(thumbnail_directory + "/" + title.replace(" ", "") + ".png", "wb")
            minia.write(content)
            minia.close()
            log_message.set("Successfully downloaded: " + str(title) + ".png")
            print("Successfully downloaded: " + str(title) + ".png")
        except Exception as e:
            log_message.set(f"An error occurred: {e}")

root = tk.Tk()

root.title("YouTool")
root.geometry("600x400")
root.wm_iconbitmap("icon.ico")

icon = tk.PhotoImage(file="logo.png")
icon = icon.subsample(4, 4)

logo = tk.Label(root, image=icon)
logo.pack(pady=5)

label = tk.Label(root, text="YouTool", font=("Arial", 20))
label.pack()

#Download Video Method
label = tk.Label(root, text="Download Video", font=("Arial", 12))
label.pack()

link_input = tk.Entry(root)
link_input.pack()

download_button = tk.Button(root, text="Download", command=download_youtube_video)
download_button.pack(pady=2)

#Download Thumbnail
label = tk.Label(root, text="Download Thumbnail", font=("Arial", 12))
label.pack()

link_input = tk.Entry(root)
link_input.pack()

download_button = tk.Button(root, text="Download", command=download_youtube_thumbnail)
download_button.pack(pady=2)

#Extre
log_message = tk.StringVar()
error_label = tk.Label(root, textvariable=log_message)
error_label.pack(pady=5)


download_button = tk.Button(root, text="@GaelHF")
download_button.pack(pady=5)

root.mainloop()