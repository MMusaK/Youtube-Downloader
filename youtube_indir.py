import os
import threading
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import subprocess
import sys

# --- EXE İÇİNDEKİ DOSYALARA ERİŞİM ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- AYARLARI KAYDETME ---
CONFIG_FILE = "settings_config.json"

def ayarları_yukle():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("download_path")
        except: return None
    return None

def ayarları_kaydet(path):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"download_path": path}, f, ensure_ascii=False, indent=4)
    except: pass

# --- YT-DLP KONTROLÜ ---
try:
    from yt_dlp import YoutubeDL
except ImportError:
    messagebox.showerror("Hata", "yt-dlp kütüphanesi eksik!")
    sys.exit()

# =========================
# PLAYLIST SEÇİM PENCERESİ
# =========================
class PlaylistSecici(tk.Toplevel):
    def __init__(self, parent, entries):
        super().__init__(parent)
        self.title("Playlist İçeriği Seçin")
        self.geometry("650x550")
        self.minsize(400, 300)
        self.configure(bg="#1A1A2E")
        self.result = None
        self.history = [] 
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Üst Panel
        top_frame = tk.Frame(self, bg="#1A1A2E")
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        btn_style = {"bg": "#333355", "fg": "white", "relief": "flat", "padx": 10, "pady": 5}
        tk.Button(top_frame, text="Hepsini Seç", command=self.hepsini_sec, **btn_style).pack(side="left", padx=2)
        tk.Button(top_frame, text="Hiçbirini Seçme", command=self.hicbirini_secme, **btn_style).pack(side="left", padx=2)
        tk.Button(top_frame, text="Geri Al", command=self.geri_al, **btn_style).pack(side="left", padx=2)

        # Liste Alanı
        self.canvas_container = tk.Frame(self, bg="#252542")
        self.canvas_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        self.canvas = tk.Canvas(self.canvas_container, bg="#252542", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.canvas_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#252542")

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", tags="self.frame")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.bind_all("<MouseWheel>", self._on_mousewheel)

        self.vars = []
        for item in entries:
            var = tk.BooleanVar(value=True)
            var.trace_add("write", lambda *args, v=var: self._manuel_kayit(v))
            
            title = item.get('title') if item.get('title') else "Başlıksız Video"
            cb = tk.Checkbutton(self.scrollable_frame, text=title, variable=var, 
                               bg="#252542", fg="white", selectcolor="#1A1A2E", 
                               activebackground="#333355", activeforeground="white",
                               anchor="w", justify="left", font=("Segoe UI", 10))
            cb.pack(fill="x", padx=5, pady=2)
            self.vars.append((var, item.get('url') if item.get('url') else item.get('webpage_url')))

        # Alt Buton
        self.indir_btn = tk.Button(self, text="SEÇİLENLERİ İNDİR", command=self.onayla, 
                                   bg="#00E676", fg="#1A1A2E", font=("Segoe UI", 11, "bold"), pady=10)
        self.indir_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        self._toplu_islem_kaydet()
        self.ignore_trace = False 

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.iptal)
        self.wait_window()

    def _manuel_kayit(self, var):
        if not self.ignore_trace:
            self._toplu_islem_kaydet()

    def _toplu_islem_kaydet(self):
        mevcut_durum = [v.get() for v, _ in self.vars]
        if not self.history or self.history[-1] != mevcut_durum:
            self.history.append(mevcut_durum)
            if len(self.history) > 30: self.history.pop(0)

    def geri_al(self):
        if len(self.history) > 1:
            self.ignore_trace = True 
            self.history.pop() 
            onceki_durum = self.history[-1] 
            for i, durum in enumerate(onceki_durum):
                self.vars[i][0].set(durum)
            self.ignore_trace = False

    def hepsini_sec(self):
        self.ignore_trace = True
        for v, _ in self.vars: v.set(True)
        self.ignore_trace = False
        self._toplu_islem_kaydet()

    def hicbirini_secme(self):
        self.ignore_trace = True
        for v, _ in self.vars: v.set(False)
        self.ignore_trace = False
        self._toplu_islem_kaydet()

    def _on_frame_configure(self, event):
        self.canvas.itemconfig("self.frame", width=self.canvas.winfo_width())
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def onayla(self):
        self.result = [url for v, url in self.vars if v.get()]
        self.destroy()

    def iptal(self):
        self.result = []
        self.destroy()

# =========================
# ANA DASHBOARD
# =========================
root = tk.Tk()
root.title("Medya İndirici Dashboard - Kararlı Sürüm")
root.geometry("850x800")
root.configure(bg="#1A1A2E")

style = ttk.Style(root)
style.theme_use("clam")
BG_COLOR, CARD_COLOR, ACCENT_COLOR, TEXT_COLOR = "#1A1A2E", "#252542", "#00E676", "#FFFFFF"

style.configure("TFrame", background=BG_COLOR)
style.configure("Card.TFrame", background=CARD_COLOR, relief="flat")
style.configure("TLabel", background=CARD_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))
style.configure("Header.TLabel", background=CARD_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 16, "bold"))
style.configure("SubHeader.TLabel", background=CARD_COLOR, foreground=ACCENT_COLOR, font=("Segoe UI", 11, "bold"))
style.configure("Green.TButton", background=ACCENT_COLOR, foreground="#1A1A2E", font=("Segoe UI", 12, "bold"))
style.configure("Control.TButton", background="#333355", foreground=TEXT_COLOR, font=("Segoe UI", 10))
style.configure("Horizontal.TProgressbar", troughcolor="#333355", background=ACCENT_COLOR, thickness=20)

main_container = ttk.Frame(root, style="TFrame", padding=30)
main_container.pack(fill="both", expand=True)

saved_path = ayarları_yukle()
saveto_path = tk.StringVar(value=saved_path if saved_path else "")
hiz_var = tk.StringVar(value="Hız: 0.00 Mbps")
counter_var = tk.StringVar(value="Bekliyor...")
cookie_path_var = tk.StringVar(value="")

def temizle_ansi(metin):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', str(metin))

def dizin_sec():
    dizin = filedialog.askdirectory()
    if dizin:
        saveto_path.set(dizin)
        ayarları_kaydet(dizin)

def cerez_dosyasi_sec():
    path = filedialog.askopenfilename(title="Cookies.txt Seç", filetypes=[("Metin Dosyaları", "*.txt")])
    if path:
        cookie_path_var.set(path)
        messagebox.showinfo("Başarılı", "Manuel çerez dosyası tanımlandı.")

def kalite_kontrol(event=None):
    if format_var.get() == "mp3":
        q_cb.pack_forget()
    else:
        q_cb.pack(fill="x", pady=5)

def indir_islemi():
    raw_links = url_text.get("1.0", tk.END).splitlines()
    links = [link.strip() for link in raw_links if link.strip()]
    if not links:
        messagebox.showwarning("Uyarı", "Lütfen en az bir link yapıştırın.")
        return
    final_path = saveto_path.get()
    if not final_path:
        final_path = os.path.join(os.path.expanduser("~"), "Desktop", "Medya Indirilenler")
    
    def run():
        try:
            os.makedirs(final_path, exist_ok=True)
            isleme_alinacak_linkler = []
            
            for l in links:
                if "list=" in l or "playlist" in l:
                    root.after(0, lambda: counter_var.set("🔍 Liste taranıyor..."))
                    extract_opts = {"quiet": True, "extract_flat": True, "nocheckcertificate": True}
                    if cookie_path_var.get(): extract_opts["cookiefile"] = cookie_path_var.get()
                    
                    with YoutubeDL(extract_opts) as ydl:
                        info = ydl.extract_info(l, download=False)
                        if info and 'entries' in info:
                            entries = list(info['entries'])
                            res_list = []
                            finished_event = threading.Event()
                            def open_dialog():
                                dialog = PlaylistSecici(root, entries)
                                res_list.append(dialog.result)
                                finished_event.set()
                            root.after(0, open_dialog)
                            finished_event.wait()
                            seçilenler = res_list[0]
                            if seçilenler: isleme_alinacak_linkler.extend(seçilenler)
                        else: isleme_alinacak_linkler.append(l)
                else:
                    isleme_alinacak_linkler.append(l)

            if not isleme_alinacak_linkler:
                root.after(0, lambda: counter_var.set("❌ İşlem iptal edildi"))
                return

            total_count = len(isleme_alinacak_linkler)
            for index, url in enumerate(isleme_alinacak_linkler, 1):
                root.after(0, lambda i=index, t=total_count: counter_var.set(f"📊 İndirilen: {i}/{t} video"))
                
                opts = {
                    # Playlist adına klasör açma yapısı güçlendirildi
                    "outtmpl": os.path.join(final_path, "%(playlist_title,playlist|İndirilenler)s", "%(title)s.%(ext)s"),
                    "progress_hooks": [progress_hook],
                    "ignoreerrors": True,
                    "nocheckcertificate": True,
                    "ffmpeg_location": resource_path("ffmpeg.exe"),
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                    "headers": {"User-Agent": "Mozilla/5.0"}
                }

                if cookie_path_var.get():
                    opts["cookiefile"] = cookie_path_var.get()
                elif "x.com" in url or "twitter.com" in url:
                    opts["cookiesfrombrowser"] = ("chrome",)

                if format_var.get() == "mp3":
                    opts.update({
                        "format": "bestaudio/best",
                        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
                    })
                else:
                    q = quality_var.get()[:-1]
                    opts.update({"format": f"bestvideo[height<={q}]+bestaudio/best / best[height<={q}]"})

                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
            
            root.after(0, lambda: counter_var.set("✅ Tüm işlemler tamamlandı"))
            root.after(0, lambda: messagebox.showinfo("Başarılı", "Tüm medya içerikleri başarıyla indirildi!"))
        except Exception as e:
            root.after(0, lambda m=str(e)[:200]: messagebox.showerror("Hata", m))
    threading.Thread(target=run, daemon=True).start()

def progress_hook(d):
    if d["status"] == "downloading":
        yuzde_temiz = temizle_ansi(d.get("_percent_str", "0%")).replace("%","").strip()
        hiz_temiz = temizle_ansi(d.get('_speed_str', '0MB/s'))
        try:
            p_float = float(yuzde_temiz)
            root.after(0, lambda: video_progress.config(value=p_float))
            root.after(0, lambda: hiz_var.set(f"Hız: {hiz_temiz} | İçeriğin %{yuzde_temiz} indirildi"))
        except: pass

# --- GUI Yerleşimi ---
top_card = ttk.Frame(main_container, style="Card.TFrame", padding=20)
top_card.pack(fill="both", expand=True, pady=(0, 20))
ttk.Label(top_card, text="TOPLU MEDYA İNDİRİCİ", style="Header.TLabel").pack(pady=(0, 10))
url_text = tk.Text(top_card, bg="#333355", fg=TEXT_COLOR, insertbackground=TEXT_COLOR, font=("Segoe UI", 10), height=8, borderwidth=0)
url_text.pack(fill="both", expand=True, pady=10)
path_frame = ttk.Frame(top_card, style="Card.TFrame")
path_frame.pack(fill="x", pady=5)
path_entry = tk.Entry(path_frame, textvariable=saveto_path, bg="#1A1A2E", fg=ACCENT_COLOR, font=("Segoe UI", 9), borderwidth=0, state="readonly")
path_entry.pack(side="left", fill="x", expand=True, ipady=5)
ttk.Button(path_frame, text="📁 Konum Seç", command=dizin_sec, style="Control.TButton").pack(side="right", padx=(5, 0))
ttk.Button(top_card, text="🍪 Manuel Cookies.txt Tanımla (Kesin Çözüm)", command=cerez_dosyasi_sec, style="Control.TButton").pack(fill="x", pady=5)
mid_frame = ttk.Frame(main_container, style="TFrame")
mid_frame.pack(fill="x", pady=10)
settings_card = ttk.Frame(mid_frame, style="Card.TFrame", padding=20)
settings_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
format_var = tk.StringVar(value="mp4")
fmt_cb = ttk.Combobox(settings_card, textvariable=format_var, values=["mp4", "mp3"], state="readonly")
fmt_cb.pack(fill="x", pady=5)
fmt_cb.bind("<<ComboboxSelected>>", kalite_kontrol)
quality_var = tk.StringVar(value="720p")
q_cb = ttk.Combobox(settings_card, textvariable=quality_var, values=["1080p", "720p", "480p", "360p"], state="readonly")
q_cb.pack(fill="x", pady=5)
status_card = ttk.Frame(mid_frame, style="Card.TFrame", padding=20)
status_card.pack(side="right", fill="both", expand=True, padx=(10, 0))
ttk.Label(status_card, textvariable=counter_var, font=("Segoe UI", 12, "bold")).pack()
ttk.Label(status_card, textvariable=hiz_var).pack(pady=5)
bottom_card = ttk.Frame(main_container, style="Card.TFrame", padding=20)
bottom_card.pack(fill="x", pady=20)
video_progress = ttk.Progressbar(bottom_card, orient="horizontal", mode="determinate", style="Horizontal.TProgressbar")
video_progress.pack(fill="x", pady=(0, 15))
ttk.Button(bottom_card, text="🚀 TOPLU İNDİRMEYİ BAŞLAT", style="Green.TButton", command=indir_islemi).pack(fill="x", ipady=10)

if __name__ == "__main__":
    root.mainloop()