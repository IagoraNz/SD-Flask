import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import requests
import os
from io import BytesIO
from PIL import Image, ImageTk
import webbrowser

# Configurações do servidor
SERVER_URL = "http://127.0.0.1:5000"  # altere se o servidor estiver em outro IP
UPLOAD_ENDPOINT = f"{SERVER_URL}/upload"
GALLERY_ENDPOINT = f"{SERVER_URL}/videos"

class VideoClientApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cliente de Vídeo - Flask")
        self.geometry("800x600")

        self.video_path = None
        self.filter_name = tk.StringVar(value="gray")

        # --- Frame de Upload ---
        frame_upload = ttk.LabelFrame(self, text="Upload de Vídeo")
        frame_upload.pack(fill="x", padx=10, pady=10)

        ttk.Button(frame_upload, text="Selecionar Vídeo", command=self.select_video).pack(side="left", padx=5)
        ttk.Entry(frame_upload, textvariable=self.filter_name, width=20).pack(side="left", padx=5)
        ttk.Button(frame_upload, text="Enviar", command=self.upload_video).pack(side="left", padx=5)

        # --- Frame de Histórico ---
        self.frame_history = ttk.LabelFrame(self, text="Histórico de Vídeos")
        self.frame_history.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(self.frame_history, columns=("id", "filter", "original", "processed"), show="headings")
        self.tree.heading("id", text="UUID")
        self.tree.heading("filter", text="Filtro")
        self.tree.heading("original", text="Original")
        self.tree.heading("processed", text="Processado")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.open_video)

        self.refresh_history()

    def select_video(self):
        self.video_path = filedialog.askopenfilename(filetypes=[("Vídeos", "*.mp4 *.avi *.mov *.mkv")])
        if self.video_path:
            messagebox.showinfo("Selecionado", f"Arquivo selecionado:\n{self.video_path}")

    def upload_video(self):
        if not self.video_path:
            messagebox.showwarning("Aviso", "Selecione um vídeo primeiro!")
            return

        filter_name = self.filter_name.get().strip()
        if not filter_name:
            filter_name = "gray"

        with open(self.video_path, "rb") as f:
            files = {"video": (os.path.basename(self.video_path), f)}
            data = {"filter": filter_name}
            try:
                response = requests.post(UPLOAD_ENDPOINT, files=files, data=data)
                if response.status_code == 200:
                    messagebox.showinfo("Sucesso", "Vídeo enviado e processado com sucesso!")
                    self.refresh_history()
                else:
                    messagebox.showerror("Erro", f"Falha ao enviar vídeo:\n{response.text}")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

    def refresh_history(self):
        # limpa a árvore
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            resp = requests.get(GALLERY_ENDPOINT)
            if resp.status_code == 200:
                videos = resp.json()
                for v in videos:
                    self.tree.insert("", "end", values=(v["id"], v["filter"], v["original"], v["processed"]))
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível carregar o histórico:\n{e}")

    def open_video(self, event):
        item = self.tree.selection()[0]
        values = self.tree.item(item, "values")
        # abrir o vídeo original no navegador
        original_url = values[2]
        processed_url = values[3]
        if messagebox.askyesno("Abrir vídeo", "Deseja abrir o vídeo processado? (Não = Original)"):
            webbrowser.open(processed_url)
        else:
            webbrowser.open(original_url)

if __name__ == "__main__":
    app = VideoClientApp()
    app.mainloop()