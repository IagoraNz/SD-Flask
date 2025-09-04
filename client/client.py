import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import requests
import os
from io import BytesIO
from PIL import Image, ImageTk
import webbrowser

class VideoClientApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vídeos carregados")
        self.geometry("800x400")
        self.configure(bg="#f0f0f0")

        self.video_path = None
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.server_port = tk.StringVar(value="5000")
        self.filter_name = tk.StringVar(value="gray")
        
        self.create_widgets()
        self.refresh_history()

    def create_widgets(self):
        # Frame principal
        main_frame = tk.Frame(self, bg="#f0f0f0")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Título
        title_label = tk.Label(main_frame, text="Vídeos carregados", 
                              font=("Poppins", 16, "bold"), bg="#f0f0f0")
        title_label.pack(pady=(0, 20))

        # Frame superior com IP/Porta e Filtro
        top_frame = tk.Frame(main_frame, bg="#f0f0f0")
        top_frame.pack(fill="x", pady=(0, 20))

        # IP e Porta
        ip_port_frame = tk.Frame(top_frame, bg="#a8d4f0", relief="solid", bd=1)
        ip_port_frame.pack(side="left", padx=(230, 10))
        
        tk.Label(ip_port_frame, text="IP:Porta", bg="#a8d4f0", 
                font=("Poppins", 10, "bold")).pack(padx=10, pady=5)
        
        ip_entry_frame = tk.Frame(ip_port_frame, bg="#a8d4f0")
        ip_entry_frame.pack(padx=10, pady=(0, 10))
        
        ip_entry = tk.Entry(ip_entry_frame, textvariable=self.server_ip, width=12)
        ip_entry.pack(side="left")
        
        tk.Label(ip_entry_frame, text=":", bg="#a8d4f0").pack(side="left")
        
        port_entry = tk.Entry(ip_entry_frame, textvariable=self.server_port, width=6)
        port_entry.pack(side="left")

        # Filtro
        filter_frame = tk.Frame(top_frame, bg="#a8d4f0", relief="solid", bd=1)
        filter_frame.pack(side="right", padx=(0, 230))
        
        tk.Label(filter_frame, text="Selecionar Filtro", bg="#a8d4f0", 
                font=("Poppins", 10, "bold")).pack(padx=10, pady=5)
        
        # Atualizado para os filtros que existem no servidor: gray, pixelate e edges
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_name, 
                                   values=["gray", "pixelate", "edges"], width=15)
        filter_combo.pack(padx=10, pady=(0, 10))

        # Frame central - área de upload e lista de vídeos
        center_frame = tk.Frame(main_frame, bg="#f0f0f0")
        center_frame.pack(fill="both", expand=True)

        # Área de upload (lado esquerdo)
        upload_frame = tk.Frame(center_frame, bg="#e8e8e8", relief="solid", bd=1, width=200)
        upload_frame.pack(side="left", fill="y", padx=(0, 20))
        upload_frame.pack_propagate(False)

        # Ícone de upload
        upload_icon_frame = tk.Frame(upload_frame, bg="#e8e8e8")
        upload_icon_frame.pack(expand=True)

        # Criar um ícone de upload simples
        icon_canvas = tk.Canvas(upload_icon_frame, width=60, height=60, 
                               bg="#e8e8e8", highlightthickness=0)
        icon_canvas.pack(pady=20)
        
        # Desenhar seta para cima
        icon_canvas.create_rectangle(25, 35, 35, 50, fill="#a0a0a0", outline="#a0a0a0")
        icon_canvas.create_polygon([30, 20, 20, 35, 40, 35], fill="#a0a0a0", outline="#a0a0a0")

        upload_label = tk.Label(upload_icon_frame, text="Procure um vídeo", 
                               bg="#e8e8e8", font=("Poppins", 12, "bold"))
        upload_label.pack()

        # Botão de buscar
        search_btn = tk.Button(upload_frame, text="Buscar", bg="#a8d4f0", 
                              command=self.select_video, width=10, font=("Poppins", 10, "bold"))
        search_btn.pack(pady=20)

        # Lista de vídeos (lado direito)
        videos_frame = tk.Frame(center_frame, bg="#f0f0f0")
        videos_frame.pack(side="right", fill="both", expand=True)

        # Frame para cada vídeo
        self.videos_list_frame = tk.Frame(videos_frame, bg="#f0f0f0")
        self.videos_list_frame.pack(fill="both", expand=True)

        # Scrollbar para a lista
        scrollbar = ttk.Scrollbar(videos_frame)
        scrollbar.pack(side="right", fill="y")

        # Canvas para scroll
        self.canvas = tk.Canvas(videos_frame, bg="#f0f0f0", yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.canvas.yview)

        # Frame interno do canvas
        self.inner_frame = tk.Frame(self.canvas, bg="#f0f0f0")
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        # Bind para atualizar scroll region
        self.inner_frame.bind('<Configure>', self._configure_scroll)
        self.canvas.bind('<Configure>', self._configure_canvas)

    def _configure_scroll(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _configure_canvas(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_frame, width=canvas_width)

    def get_server_url(self):
        ip = self.server_ip.get().strip()
        port = self.server_port.get().strip()
        return f"http://{ip}:{port}"

    def select_video(self):
        self.video_path = filedialog.askopenfilename(
            filetypes=[("Vídeos", "*.mp4 *.avi *.mov *.mkv")])
        if self.video_path:
            self.upload_video()

    def upload_video(self):
        if not self.video_path:
            messagebox.showwarning("Aviso", "Selecione um vídeo primeiro!")
            return

        filter_name = self.filter_name.get().strip()
        if not filter_name:
            filter_name = "gray"

        server_url = self.get_server_url()
        upload_endpoint = f"{server_url}/upload"

        with open(self.video_path, "rb") as f:
            files = {"video": (os.path.basename(self.video_path), f)}
            data = {"filter": filter_name}
            try:
                response = requests.post(upload_endpoint, files=files, data=data)
                if response.status_code == 200:
                    messagebox.showinfo("Sucesso", "Vídeo enviado e processado com sucesso!")
                    self.refresh_history()
                else:
                    messagebox.showerror("Erro", f"Falha ao enviar vídeo:\n{response.text}")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

    def refresh_history(self):
        # Limpar lista atual
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

        server_url = self.get_server_url()
        gallery_endpoint = f"{server_url}/videos"

        try:
            resp = requests.get(gallery_endpoint)
            if resp.status_code == 200:
                videos = resp.json()
                for i, video in enumerate(videos):
                    self.create_video_item(video, i)
        except Exception as e:
            error_label = tk.Label(self.inner_frame, 
                                 text=f"Erro ao carregar vídeos: {e}", 
                                 bg="#f0f0f0", fg="red")
            error_label.pack(pady=10)

    def create_video_item(self, video, index):
        # Frame para cada item de vídeo
        video_frame = tk.Frame(self.inner_frame, bg="#e8f4fd", relief="solid", bd=1)
        video_frame.pack(fill="x", padx=10, pady=5)

        # Frame interno
        content_frame = tk.Frame(video_frame, bg="#e8f4fd")
        content_frame.pack(fill="x", padx=10, pady=10)

        # Ícone do vídeo (lado esquerdo)
        icon_frame = tk.Frame(content_frame, bg="#a8d4f0", width=40, height=40)
        icon_frame.pack(side="left", padx=(0, 10))
        icon_frame.pack_propagate(False)

        icon_label = tk.Label(icon_frame, text="MP4", bg="#a8d4f0", 
                             font=("Poppins", 8, "bold"))
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Informações do vídeo
        info_frame = tk.Frame(content_frame, bg="#e8f4fd")
        info_frame.pack(side="left", fill="x", expand=True)

        # Nome do arquivo
        filename = video.get("original", "").split("/")[-1] if video.get("original") else "video.mp4"
        name_label = tk.Label(info_frame, text=filename, 
                             bg="#e8f4fd", font=("Poppins", 10, "bold"))
        name_label.pack(anchor="w")

        # Bind para duplo clique
        def on_double_click(event):
            self.open_video(video)

        video_frame.bind("<Double-Button-1>", on_double_click)
        content_frame.bind("<Double-Button-1>", on_double_click)

    def open_video(self, video):
        original_url = video.get("original", "")
        processed_url = video.get("processed", "")
        
        if messagebox.askyesno("Abrir vídeo", "Deseja abrir o vídeo processado? (Não = Original)"):
            if processed_url:
                webbrowser.open(processed_url)
            else:
                messagebox.showwarning("Aviso", "Vídeo processado não disponível")
        else:
            if original_url:
                webbrowser.open(original_url)
            else:
                messagebox.showwarning("Aviso", "Vídeo original não disponível")

    def remove_video(self, video):
        if messagebox.askyesno("Remover", "Deseja remover este vídeo?"):
            try:
                server_url = self.get_server_url()
                delete_endpoint = f"{server_url}/delete/{video['id']}"
                response = requests.delete(delete_endpoint)
                if response.status_code == 200:
                    messagebox.showinfo("Sucesso", "Vídeo removido!")
                    self.refresh_history()
                else:
                    messagebox.showerror("Erro", "Não foi possível remover o vídeo")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

if __name__ == "__main__":
    app = VideoClientApp()
    app.mainloop()