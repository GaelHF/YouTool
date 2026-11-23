import os
import sys
import shutil
import io
import ssl
import certifi
import threading
import urllib.request
import customtkinter as ctk
import yt_dlp
from tkinter import filedialog, StringVar
from PIL import Image

ctk.set_default_color_theme("blue")

# Certificats de certifi : évite les erreurs SSL (surtout sur macOS) sans désactiver la vérification
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

ACCENT       = "#e94560"
ACCENT_HOVER = "#c73652"

def _find_ffmpeg_dir():
    """Dossier contenant ffmpeg : embarqué (build) > ./ffmpeg > PATH > Homebrew."""
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "bin"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg"))
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(os.path.dirname(found))
    candidates += ["/opt/homebrew/bin", "/usr/local/bin"]
    for d in candidates:
        if os.path.isfile(os.path.join(d, exe)):
            return d
    return None


_FFMPEG_DIR = _find_ffmpeg_dir()

YDL_BASE = {
    "extractor_args": {"youtube": {"player_client": ["android_vr", "android"]}},
}
if _FFMPEG_DIR:
    YDL_BASE["ffmpeg_location"] = _FFMPEG_DIR

# ── Traductions ───────────────────────────────────────────────────────────────
LANGS = {
    "fr": {
        "tab_video"      : "Vidéo / Audio",
        "tab_thumb"      : "Miniature",
        "yt_link"        : "Lien YouTube",
        "format"         : "Format",
        "quality"        : "Qualité",
        "folder"         : "Dossier de téléchargement",
        "browse"         : "Parcourir",
        "download"       : "⬇  Télécharger",
        "preview"        : "Aperçu",
        "fmt_video"      : "Vidéo (MP4)",
        "fmt_audio"      : "Audio (MP3)",
        "q_best"         : "Meilleure qualité",
        "starting"       : "Démarrage…",
        "done"           : "Terminé ✓",
        "finalizing"     : "Finalisation…",
        "error"          : "Erreur",
        "downloading"    : "Téléchargement…",
        "loading"        : "Chargement…",
        "warn_url"       : "⚠  Veuillez entrer un lien YouTube.",
        "log_fetching"   : "🔍  Récupération de la miniature…",
        "log_saved"      : "✅  Sauvegardé dans : ",
        "log_thumb_saved": "✅  Miniature sauvegardée : ",
    },
    "en": {
        "tab_video"      : "Video / Audio",
        "tab_thumb"      : "Thumbnail",
        "yt_link"        : "YouTube Link",
        "format"         : "Format",
        "quality"        : "Quality",
        "folder"         : "Download folder",
        "browse"         : "Browse",
        "download"       : "⬇  Download",
        "preview"        : "Preview",
        "fmt_video"      : "Video (MP4)",
        "fmt_audio"      : "Audio (MP3)",
        "q_best"         : "Best quality",
        "starting"       : "Starting…",
        "done"           : "Done ✓",
        "finalizing"     : "Finalizing…",
        "error"          : "Error",
        "downloading"    : "Downloading…",
        "loading"        : "Loading…",
        "warn_url"       : "⚠  Please enter a YouTube link.",
        "log_fetching"   : "🔍  Fetching thumbnail…",
        "log_saved"      : "✅  Saved to: ",
        "log_thumb_saved": "✅  Thumbnail saved: ",
    },
}


def _resource_path(name):
    """Chemin d'une ressource, compatible PyInstaller (_MEIPASS)."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


ICON_PATH = _resource_path("icon.ico")


def _make_logo(size=52):
    img = Image.open(ICON_PATH).convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    return img


class YouTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTool")
        self.geometry("700x620")
        self.resizable(False, False)
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._appearance = "dark"
        ctk.set_appearance_mode(self._appearance)

        self._lang       = "fr"
        self.download_path = os.path.expanduser("~/Downloads")
        self.is_busy     = False
        # État interne format/qualité (indépendant de la langue)
        self._fmt_is_audio  = False
        self._quality_idx   = 0   # 0 = meilleure

        self._build_ui()

    # ── Fermeture ─────────────────────────────────────────────────────────────

    def _on_close(self):
        """Ferme la fenêtre et tue tout ce qui tourne encore (threads, ffmpeg)."""
        try:
            self.withdraw()
            self.quit()
            self.destroy()
        except Exception:
            pass
        try:
            if sys.platform == "win32":
                # Tue ce process et ses enfants (ffmpeg lancé par yt-dlp)
                import subprocess
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(os.getpid())],
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif os.getpgid(0) == os.getpid():
                import signal
                os.killpg(os.getpid(), signal.SIGKILL)
        except Exception:
            pass
        os._exit(0)

    # ── Raccourci traduction ──────────────────────────────────────────────────

    def t(self, key):
        return LANGS[self._lang][key]

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header fixe (jamais reconstruit)
        self.header = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=0, height=72)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        logo_img = _make_logo(52)
        self._logo_ref = ctk.CTkImage(light_image=logo_img, dark_image=logo_img,
                                      size=(logo_img.width, logo_img.height))
        ctk.CTkLabel(self.header, image=self._logo_ref, text="").place(
            relx=0.5, rely=0.5, anchor="e", x=-6)

        ctk.CTkLabel(self.header, text="YouTool",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=ACCENT).place(relx=0.5, rely=0.5, anchor="w", x=6)

        # Bouton langue (FR / EN)
        self.lang_btn = ctk.CTkButton(
            self.header, text="EN", width=42, height=32, corner_radius=8,
            fg_color="#16213e", hover_color="#0f3460",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_lang,
        )
        self.lang_btn.place(relx=0.88, rely=0.5, anchor="e")

        # Bouton thème
        self.theme_btn = ctk.CTkButton(
            self.header, text="☀", width=36, height=36, corner_radius=18,
            fg_color="transparent", hover_color="#2a2a4e",
            font=ctk.CTkFont(size=18), command=self._toggle_theme,
        )
        self.theme_btn.place(relx=0.96, rely=0.5, anchor="e")

        # Zone centrale (onglets + log) — reconstruite à chaque changement de langue
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        self._build_body()

    def _build_body(self):
        # Vider l'ancienne UI
        for w in self.body.winfo_children():
            w.destroy()

        # Onglets
        self.tabview = ctk.CTkTabview(self.body, anchor="nw", height=500)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(12, 0))
        self.tabview.add(self.t("tab_video"))
        self.tabview.add(self.t("tab_thumb"))

        self._build_video_tab(self.tabview.tab(self.t("tab_video")))
        self._build_thumb_tab(self.tabview.tab(self.t("tab_thumb")))

        # Log
        self.log_box = ctk.CTkTextbox(
            self.body, height=80,
            font=ctk.CTkFont(size=11, family="Courier"),
            fg_color="#0d0d1a", text_color="#7ec8e3",
        )
        self.log_box.pack(fill="x", padx=20, pady=(6, 12))
        self.log_box.configure(state="disabled")

    def _build_video_tab(self, tab):
        p = ctk.CTkFrame(tab, fg_color="transparent")
        p.pack(fill="both", expand=True)

        ctk.CTkLabel(p, text=self.t("yt_link"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(4, 4))
        self.v_url = ctk.CTkEntry(p, placeholder_text="https://www.youtube.com/watch?v=...",
                                  height=40, font=ctk.CTkFont(size=13))
        self.v_url.pack(fill="x", pady=(0, 12))

        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))

        # Format
        ff = ctk.CTkFrame(row, fg_color="transparent")
        ff.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(ff, text=self.t("format"),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.v_fmt = StringVar(value=self.t("fmt_audio") if self._fmt_is_audio else self.t("fmt_video"))
        self.v_fmt_menu = ctk.CTkOptionMenu(
            ff, values=[self.t("fmt_video"), self.t("fmt_audio")],
            variable=self.v_fmt, command=self._on_fmt_change, height=36)
        self.v_fmt_menu.pack(fill="x", pady=(2, 0))

        # Qualité
        qf = ctk.CTkFrame(row, fg_color="transparent")
        qf.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(qf, text=self.t("quality"),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.v_quality = StringVar(value=self._current_quality_label())
        self.v_quality_menu = ctk.CTkOptionMenu(
            qf, values=self._quality_values(), variable=self.v_quality, height=36,
            command=self._on_quality_change)
        self.v_quality_menu.pack(fill="x", pady=(2, 0))

        # Dossier
        ctk.CTkLabel(p, text=self.t("folder"),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        pr = ctk.CTkFrame(p, fg_color="transparent")
        pr.pack(fill="x", pady=(0, 12))
        self.v_path_lbl = ctk.CTkLabel(pr, text=self.download_path,
                                        font=ctk.CTkFont(size=11), text_color="#aaaaaa", anchor="w")
        self.v_path_lbl.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(pr, text=self.t("browse"), width=90, height=32,
                      command=lambda: self._choose_folder("video"),
                      fg_color="#16213e", hover_color="#0f3460").pack(side="right")

        # Progression
        self.v_bar = ctk.CTkProgressBar(p, height=8)
        self.v_bar.pack(fill="x", pady=(0, 4))
        self.v_bar.set(0)
        self.v_bar_lbl = ctk.CTkLabel(p, text="", font=ctk.CTkFont(size=11), text_color="#aaaaaa")
        self.v_bar_lbl.pack(anchor="w", pady=(0, 10))

        self.v_btn = ctk.CTkButton(p, text=self.t("download"), height=44,
                                   font=ctk.CTkFont(size=14, weight="bold"),
                                   fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                   command=self._start_video_download)
        self.v_btn.pack(fill="x")

    def _build_thumb_tab(self, tab):
        p = ctk.CTkFrame(tab, fg_color="transparent")
        p.pack(fill="both", expand=True)

        ctk.CTkLabel(p, text=self.t("yt_link"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(4, 4))
        self.t_url = ctk.CTkEntry(p, placeholder_text="https://www.youtube.com/watch?v=...",
                                  height=40, font=ctk.CTkFont(size=13))
        self.t_url.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(p, text=self.t("folder"),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        tr = ctk.CTkFrame(p, fg_color="transparent")
        tr.pack(fill="x", pady=(0, 12))
        self.t_path_lbl = ctk.CTkLabel(tr, text=self.download_path,
                                        font=ctk.CTkFont(size=11), text_color="#aaaaaa", anchor="w")
        self.t_path_lbl.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(tr, text=self.t("browse"), width=90, height=32,
                      command=lambda: self._choose_folder("thumb"),
                      fg_color="#16213e", hover_color="#0f3460").pack(side="right")

        self.thumb_preview = ctk.CTkLabel(p, text="", width=320, height=180,
                                          fg_color="#0d0d1a", corner_radius=8)
        self.thumb_preview.pack(pady=(0, 12))
        self.thumb_title_lbl = ctk.CTkLabel(p, text="", font=ctk.CTkFont(size=11),
                                             text_color="#aaaaaa")
        self.thumb_title_lbl.pack(pady=(0, 8))

        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self.t_preview_btn = ctk.CTkButton(row, text=self.t("preview"), height=44,
                                           font=ctk.CTkFont(size=13, weight="bold"),
                                           fg_color="#16213e", hover_color="#0f3460",
                                           command=self._preview_thumbnail)
        self.t_preview_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.t_btn = ctk.CTkButton(row, text=self.t("download"), height=44,
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                   command=self._start_thumb_download)
        self.t_btn.pack(side="left", fill="x", expand=True)

    # ── Helpers qualité / format ──────────────────────────────────────────────

    _VIDEO_QUALITIES = ["best", "1080p", "720p", "480p", "360p"]
    _AUDIO_QUALITIES = ["best", "320kbps", "192kbps", "128kbps"]

    def _quality_values(self):
        keys = self._AUDIO_QUALITIES if self._fmt_is_audio else self._VIDEO_QUALITIES
        return [self.t("q_best") if k == "best" else k for k in keys]

    def _current_quality_label(self):
        idx = min(self._quality_idx, len(self._quality_values()) - 1)
        return self._quality_values()[idx]

    def _internal_quality(self):
        keys = self._AUDIO_QUALITIES if self._fmt_is_audio else self._VIDEO_QUALITIES
        idx = min(self._quality_idx, len(keys) - 1)
        return keys[idx]

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _toggle_lang(self):
        self._lang = "en" if self._lang == "fr" else "fr"
        self.lang_btn.configure(text="FR" if self._lang == "en" else "EN")
        self._build_body()

    def _toggle_theme(self):
        self._appearance = "light" if self._appearance == "dark" else "dark"
        ctk.set_appearance_mode(self._appearance)
        self.theme_btn.configure(text="☀" if self._appearance == "dark" else "☾")

    def _choose_folder(self, target):
        folder = filedialog.askdirectory(initialdir=self.download_path)
        if folder:
            self.download_path = folder
            if target == "video":
                self.v_path_lbl.configure(text=folder)
            else:
                self.t_path_lbl.configure(text=folder)

    def _on_fmt_change(self, value):
        self._fmt_is_audio = (value == self.t("fmt_audio"))
        self._quality_idx  = 0
        self.v_quality_menu.configure(values=self._quality_values())
        self.v_quality.set(self._quality_values()[0])

    def _on_quality_change(self, value):
        opts = self._quality_values()
        self._quality_idx = opts.index(value) if value in opts else 0

    def _log(self, msg):
        # Tkinter n'est pas thread-safe : depuis un thread, on repasse par la boucle UI
        if threading.current_thread() is not threading.main_thread():
            self.after(0, self._log, msg)
            return
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ── Onglet Vidéo ──────────────────────────────────────────────────────────

    def _start_video_download(self):
        url = self.v_url.get().strip()
        if not url:
            self._log(self.t("warn_url"))
            return
        if self.is_busy:
            return
        self.is_busy = True
        self.v_btn.configure(state="disabled", text=self.t("downloading"))
        self.v_bar.set(0)
        self.v_bar_lbl.configure(text=self.t("starting"))
        threading.Thread(target=self._download_video, args=(url,), daemon=True).start()

    def _build_ydl_opts(self):
        opts = dict(YDL_BASE)
        opts["outtmpl"] = os.path.join(self.download_path, "%(title)s.%(ext)s")
        q = self._internal_quality()
        if self._fmt_is_audio:
            # "0" = meilleure qualité VBR ; sinon débit constant en kb/s
            aq = {"320kbps": "320", "192kbps": "192", "128kbps": "128"}.get(q, "0")
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                        "preferredcodec": "mp3", "preferredquality": aq}]
        else:
            quality_map = {
                "best" : "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
                "720p" : "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
                "480p" : "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
                "360p" : "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
            }
            opts["format"] = quality_map.get(q, "best")
            opts["merge_output_format"] = "mp4"
        return opts

    def _download_video(self, url):
        opts = self._build_ydl_opts()
        opts["progress_hooks"] = [self._video_progress_hook]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "") if info else ""
                if title:
                    self._log(f"📥  {title}")
            self.after(0, lambda: self.v_bar.set(1.0))
            self.after(0, lambda: self.v_bar_lbl.configure(text=self.t("done")))
            self._log(self.t("log_saved") + self.download_path)
        except Exception as e:
            self.after(0, lambda: self.v_bar.set(0))
            self.after(0, lambda: self.v_bar_lbl.configure(text=self.t("error")))
            self._log(f"❌  {e}")
        finally:
            self.is_busy = False
            self.after(0, lambda: self.v_btn.configure(state="normal", text=self.t("download")))

    def _video_progress_hook(self, d):
        if d["status"] == "downloading":
            total      = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed      = d.get("speed") or 0
            eta        = d.get("eta") or 0
            if total > 0:
                pct = downloaded / total
                s   = f"{speed / 1_048_576:.1f} Mo/s" if speed else ""
                e   = f"  ETA {eta}s" if eta else ""
                self.after(0, lambda p=pct, txt=f"{pct*100:.1f}%  {s}{e}": (
                    self.v_bar.set(p), self.v_bar_lbl.configure(text=txt)
                ))
        elif d["status"] == "finished":
            self.after(0, lambda: (
                self.v_bar.set(0.99),
                self.v_bar_lbl.configure(text=self.t("finalizing"))
            ))

    # ── Onglet Miniature ──────────────────────────────────────────────────────

    def _get_thumb_url(self, url):
        opts = {**YDL_BASE, "quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info.get("thumbnail", ""), info.get("title", "thumbnail")

    def _preview_thumbnail(self):
        url = self.t_url.get().strip()
        if not url:
            self._log(self.t("warn_url"))
            return
        if self.is_busy:
            return
        self.t_preview_btn.configure(state="disabled", text=self.t("loading"))
        self._log(self.t("log_fetching"))
        threading.Thread(target=self._load_preview, args=(url,), daemon=True).start()

    def _load_preview(self, url):
        try:
            thumb_url, title = self._get_thumb_url(url)
            with urllib.request.urlopen(thumb_url, context=_SSL_CTX) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data))
            img.thumbnail((320, 180))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self._thumb_img_ref = ctk_img
            self.after(0, lambda: self.thumb_preview.configure(image=ctk_img, text=""))
            self.after(0, lambda: self.thumb_title_lbl.configure(text=title))
            self._log(f"🖼  {title}")
        except Exception as e:
            self._log(f"❌  {e}")
        finally:
            self.after(0, lambda: self.t_preview_btn.configure(
                state="normal", text=self.t("preview")))

    def _start_thumb_download(self):
        url = self.t_url.get().strip()
        if not url:
            self._log(self.t("warn_url"))
            return
        if self.is_busy:
            return
        self.is_busy = True
        self.t_btn.configure(state="disabled", text=self.t("downloading"))
        threading.Thread(target=self._download_thumbnail, args=(url,), daemon=True).start()

    def _download_thumbnail(self, url):
        try:
            thumb_url, title = self._get_thumb_url(url)
            safe = "".join(c for c in title if c not in r'\/:*?"<>|' and c.isprintable())
            safe = safe.strip().rstrip(".")[:150] or "thumbnail"
            dest = os.path.join(self.download_path, f"{safe}.jpg")
            with urllib.request.urlopen(thumb_url, context=_SSL_CTX) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data))
            img.save(dest, "JPEG", quality=95)
            self._log(self.t("log_thumb_saved") + dest)
        except Exception as e:
            self._log(f"❌  {e}")
        finally:
            self.is_busy = False
            self.after(0, lambda: self.t_btn.configure(
                state="normal", text=self.t("download")))


if __name__ == "__main__":
    app = YouTool()
    app.mainloop()
