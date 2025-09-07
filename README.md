# 🎬 SD-Flask – Sistema Cliente/Servidor em Camadas

Este projeto implementa um sistema **cliente/servidor em três camadas** capaz de **enviar, processar e armazenar vídeos** de forma organizada.  
A ideia é permitir que um cliente gráfico envie vídeos para o servidor, que aplica filtros com **OpenCV**, armazena os resultados e mantém **metadados em SQLite**.  

## 📌 Funcionalidades

- **Cliente (Tkinter + Requests)**  
  - Seleciona e envia vídeos via HTTP para o servidor.  
  - Permite escolher o filtro desejado (ex.: escala de cinza, pixelização, bordas).  
  - Exibe o vídeo original e o processado.  
  - Mostra o histórico de vídeos enviados.  

- **Servidor (Flask + OpenCV)**  
  - Recebe vídeos e aplica filtros de processamento.  
  - Armazena vídeos em pastas organizadas por **data + UUID**.  
  - Registra metadados no banco **SQLite**.  
  - Gera **thumbnails e GIFs** para visualização rápida.  

- **Banco de Dados (SQLite)**  
  - Tabela `videos` contendo:  
    - `id (UUID)`  
    - `original_name`, `mime_type`, `size_bytes`, `duration_sec`, `fps`, `width`, `height`  
    - `filter`, `created_at`  
    - `path_original`, `path_processed`  

## 📂 Estrutura principal do projeto

```
SD-FLASK/
├── 📁 .env/
│
├── 📁 client/
│   ├── 📁 .venv/
│   ├── 🐍 client.py
│   └── 🎞️ <videos>.mp4
│
├── 📁 server/
│   ├── 📁 .venv/
│   ├── 📁 media/
│       ├── 📁 incoming/
│       ├── 📁 trash/
│       └── 📁 videos/yyyy/mm/dd/uuid/
│           ├── 🎬 original/
│           ├── 🛠️ processed/
│           ├── 🖼️ thumbs/
│           └── 📄 meta.json
│   ├── 📁 static/
│       └── 🖼️ image8.png 
│   ├── 📁 templates/
│       └── 🌐 index.html
│   ├── 🐍 app.py
│   ├── 🐍 db.py
│   ├── 🐍 processing.py
│   ├── 🐍 utils.py
│   ├── 📦 requirements.txt
│   └── 🗄️ videos.db
│
├── 📜 LICENSE
├── 📄 comandos.txt
└── 📘 README.md
```

## ⚙️ Comandos Fundamentais

### ▶️ Executando o modelo cliente-servidor
Rode preferencialmente o servidor primeiro que o cliente.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd client
python3 client.py ou python client.py

Em outro Terminal rode:
source .venv/bin/activate
cd server

python3 app.py ou python app.py

# (opcional) copie config.example.env para .env e ajuste caminhos/host/porta
python app.py
```

## 📸 Demonstração passo a passo
1. Inicie o servidor seguindo os comandos fornecidos anteriormente.
2. Inicie o cliente logo em seguida.
3. A interface do cliente será exibida:

<img width="600" height="338" alt="Interface do cliente" src="https://github.com/user-attachments/assets/a70d7cf6-7db5-437f-b2c0-bb4f5de2bcd8" />

4. Se a aplicação estiver rodando localmente, não é necessário alterar o campo IP:Porta. Caso contrário, preencha com o IP adequado:

<img width="600" height="338" alt="Campo IP:Porta" src="https://github.com/user-attachments/assets/a4389398-24ae-48dd-8062-2cee98e6e9a4" />

5. Escolha o filtro a ser aplicado no vídeo que será processado:

<img width="600" height="338" alt="Escolha do filtro" src="https://github.com/user-attachments/assets/ef7f7b9e-400e-4dfd-910c-7dc27bbf9788" />

6. Busque o vídeo de interesse clicando no botão de buscar:

<img width="600" height="338" alt="Buscar vídeo" src="https://github.com/user-attachments/assets/04f47861-6d79-485b-bef5-9b5100ee4cfc" />

7. A mensagem de vídeo carregado aparecerá:

<img width="600" height="338" alt="Vídeo carregado" src="https://github.com/user-attachments/assets/f42a169c-c00a-4717-9f47-2a158013d640" />

8. Abra a interface web do servidor para visualizar o histórico de vídeos:

<img width="600" height="338" alt="Histórico de vídeos" src="https://github.com/user-attachments/assets/2a5b24fb-6163-47f6-b139-4e07b96df1c1" />

9. Aproveite a aplicação!
