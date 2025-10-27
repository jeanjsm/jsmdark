import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys
from pathlib import Path
import random
import os
from datetime import datetime


# --- Funções do FFmpeg ---

def get_ffmpeg_path():
    """Encontra o executável do ffmpeg."""
    ffmpeg_path = "ffmpeg"
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        subprocess.run([ffmpeg_path, "-version"], check=True, capture_output=True, startupinfo=startupinfo)
        return ffmpeg_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        messagebox.showerror(
            "Erro Crítico",
            "O FFmpeg não foi encontrado no seu sistema. "
            "Por favor, instale o FFmpeg e garanta que ele esteja no PATH do sistema."
        )
        sys.exit(1)


def create_video_from_images(
        image_folder, output_path, duration_per_image, use_ken_burns, sequential,
        crf, preset, fade_enabled, fade_duration, max_duration, progress_callback, log_callback
):
    """Cria um vídeo a partir de uma pasta de imagens."""
    log_callback(f"Iniciando criação de vídeo a partir de imagens...", "info")
    log_callback(f"Pasta: {image_folder}", "debug")

    ffmpeg_path = get_ffmpeg_path()
    image_path = Path(image_folder)
    image_files = sorted(
        [f for f in image_path.iterdir() if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']])

    log_callback(f"Encontradas {len(image_files)} imagens na pasta", "info")

    if not image_files:
        log_callback("ERRO: Nenhuma imagem encontrada!", "error")
        messagebox.showerror("Erro", f"Nenhuma imagem encontrada na pasta: {image_folder}")
        return

    if not sequential:
        random.shuffle(image_files)
        log_callback("Imagens embaralhadas (ordem aleatória)", "debug")

    # Calcula quantas imagens usar baseado no tempo máximo
    if max_duration > 0:
        max_images = int(max_duration / duration_per_image)
        image_files = image_files[:max_images]
        log_callback(f"Limitado a {len(image_files)} imagens (tempo máximo: {max_duration}s)", "info")
        if not image_files:
            log_callback("ERRO: Tempo máximo muito curto!", "error")
            messagebox.showerror("Erro", "O tempo máximo é muito curto para incluir pelo menos uma imagem.")
            return

    concat_list_path = Path("./concat_list.txt")
    temp_video_files = []

    total_images = len(image_files)
    progress_step = 90 / total_images

    log_callback(f"Processando {total_images} imagens...", "info")

    with open(concat_list_path, "w", encoding="utf-8") as f_concat:
        for i, img_file in enumerate(image_files):
            temp_output = Path(f"./temp_clip_{i}.mp4")
            temp_video_files.append(temp_output)

            log_callback(f"  [{i + 1}/{total_images}] Processando: {img_file.name}", "debug")

            # Filtro de vídeo com fade
            if use_ken_burns:
                zoom = 1.2
                scaled_w = int(1920 * zoom)
                scaled_h = int(1080 * zoom)

                effects = [
                    {'x': f'(iw-ow)*(t/{duration_per_image})', 'y': '(ih-oh)/2'},
                    {'x': f'(iw-ow)*(1-(t/{duration_per_image}))', 'y': '(ih-oh)/2'},
                    {'x': '(iw-ow)/2', 'y': f'(ih-oh)*(t/{duration_per_image})'},
                    {'x': '(iw-ow)/2', 'y': f'(ih-oh)*(1-(t/{duration_per_image}))'},
                ]
                effect = random.choice(effects)
                pan_x, pan_y = effect['x'], effect['y']

                vf = (
                    f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase,"
                    f"crop=w=1920:h=1080:x='{pan_x}':y='{pan_y}',"
                )
            else:
                vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"

            # Adiciona fade in/out
            if fade_duration > 0:
                vf += f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration_per_image - fade_duration}:d={fade_duration},"

            vf += "format=yuv420p"

            cmd = [
                ffmpeg_path, "-y", "-loop", "1", "-t", str(duration_per_image),
                "-i", str(img_file), "-vf", vf, "-c:v", "libx264",
                "-preset", preset, "-crf", str(crf), "-r", "30", "-an", str(temp_output)
            ]

            cmd_str = ' '.join(str(c) for c in cmd)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                log_callback(f"AVISO: Erro ao processar {img_file.name}", "warning")
                log_callback(f"  Código de erro: {result.returncode}", "debug")
                log_callback(f"  Comando executado: {cmd_str}", "debug")
                # Mostra mais detalhes do erro - últimas linhas do stderr
                error_lines = result.stderr.strip().split('\n')
                relevant_errors = error_lines[-10:] if len(error_lines) > 10 else error_lines
                for line in relevant_errors:
                    if line.strip():
                        log_callback(f"  {line}", "debug")
            else:
                log_callback(f"  ✓ {img_file.name} processado com sucesso!", "debug")

            f_concat.write(f"file '{temp_output.resolve()}'\n")
            progress_callback(int((i + 1) * progress_step))

    log_callback("Concatenando clipes...", "info")

    # Comando final para concatenar
    final_cmd = [
        ffmpeg_path, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path), "-c", "copy"
    ]

    if max_duration > 0:
        final_cmd.extend(["-t", str(max_duration)])

    final_cmd.append(str(output_path))

    final_cmd_str = ' '.join(str(c) for c in final_cmd)

    result = subprocess.run(final_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log_callback(f"ERRO na concatenação final!", "error")
        log_callback(f"Código de erro: {result.returncode}", "error")
        log_callback(f"Comando: {final_cmd_str}", "debug")
        # Mostra as últimas linhas de erro que são mais relevantes
        error_lines = result.stderr.strip().split('\n')
        relevant_errors = error_lines[-15:] if len(error_lines) > 15 else error_lines
        for line in relevant_errors:
            if line.strip():
                log_callback(f"  {line}", "error")
    else:
        log_callback("✓ Vídeo criado com sucesso!", "success")

    progress_callback(100)

    # Limpeza
    log_callback("Limpando arquivos temporários...", "debug")
    for temp_file in temp_video_files:
        if temp_file.exists():
            os.remove(temp_file)
    if concat_list_path.exists():
        os.remove(concat_list_path)
    log_callback("Limpeza concluída", "debug")


def get_video_duration(video_path, ffmpeg_path):
    """Obtém a duração de um vídeo em segundos usando ffprobe."""
    try:
        # Usa ffprobe para pegar a duração
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except:
        pass
    return None


def create_video_from_videos_direct(
        video_folder, output_path, num_videos, sequential,
        max_duration, progress_callback, log_callback
):
    """Concatena vídeos diretamente sem recodificação (muito mais rápido)."""
    log_callback(f"Usando CONCATENAÇÃO DIRETA (sem recodificação)", "info")
    log_callback(f"Pasta: {video_folder}", "debug")

    ffmpeg_path = get_ffmpeg_path()
    video_path = Path(video_folder)
    video_files = sorted(
        [f for f in video_path.iterdir() if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']])

    log_callback(f"Encontrados {len(video_files)} vídeos na pasta", "info")

    if not video_files:
        log_callback("ERRO: Nenhum vídeo encontrado!", "error")
        messagebox.showerror("Erro", f"Nenhum vídeo encontrado na pasta: {video_folder}")
        return

    if not sequential:
        random.shuffle(video_files)
        log_callback("Vídeos embaralhados (ordem aleatória)", "debug")

    selected_videos = video_files[:num_videos]
    log_callback(f"Selecionados {len(selected_videos)} vídeos para concatenar", "info")

    if max_duration > 0:
        log_callback(f"Tempo máximo configurado: {max_duration}s", "info")

    concat_list_path = Path("./concat_list.txt")

    total_videos = len(selected_videos)
    progress_step = 90 / total_videos

    log_callback(f"Criando lista de concatenação...", "info")

    with open(concat_list_path, "w", encoding="utf-8") as f_concat:
        for i, vid_file in enumerate(selected_videos):
            log_callback(f"  [{i + 1}/{total_videos}] Adicionado: {vid_file.name}", "debug")
            f_concat.write(f"file '{vid_file.resolve()}'\n")
            progress_callback(int((i + 1) * progress_step))

    log_callback("Concatenando vídeos diretamente (sem recodificação)...", "info")

    # Comando de concatenação direta - muito mais rápido!
    final_cmd = [
        ffmpeg_path, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path), "-c", "copy"
    ]

    if max_duration > 0:
        final_cmd.extend(["-t", str(max_duration)])

    final_cmd.append(str(output_path))

    final_cmd_str = ' '.join(str(c) for c in final_cmd)

    result = subprocess.run(final_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log_callback(f"ERRO na concatenação!", "error")
        log_callback(f"Código de erro: {result.returncode}", "error")
        log_callback(f"Comando: {final_cmd_str}", "debug")
        error_lines = result.stderr.strip().split('\n')
        relevant_errors = error_lines[-15:] if len(error_lines) > 15 else error_lines
        for line in relevant_errors:
            if line.strip():
                log_callback(f"  {line}", "error")
    else:
        log_callback("✓ Vídeo criado com sucesso (concatenação direta)!", "success")

    progress_callback(100)

    # Limpeza
    log_callback("Limpando arquivos temporários...", "debug")
    if concat_list_path.exists():
        os.remove(concat_list_path)
    log_callback("Limpeza concluída", "debug")


def create_video_from_videos(
        video_folder, output_path, num_videos, sequential,
        crf, preset, fade_enabled, fade_duration, max_duration, video_speed, progress_callback, log_callback
):
    """Cria um vídeo a partir de uma pasta de outros vídeos."""
    log_callback(f"Iniciando criação de vídeo a partir de outros vídeos...", "info")
    log_callback(f"Pasta: {video_folder}", "debug")
    log_callback(f"Velocidade dos vídeos: {video_speed}x", "info")

    ffmpeg_path = get_ffmpeg_path()
    video_path = Path(video_folder)
    video_files = sorted(
        [f for f in video_path.iterdir() if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']])

    log_callback(f"Encontrados {len(video_files)} vídeos na pasta", "info")

    if not video_files:
        log_callback("ERRO: Nenhum vídeo encontrado!", "error")
        messagebox.showerror("Erro", f"Nenhum vídeo encontrado na pasta: {video_folder}")
        return

    if not sequential:
        random.shuffle(video_files)
        log_callback("Vídeos embaralhados (ordem aleatória)", "debug")

    # Limita o número de vídeos
    selected_videos = video_files[:num_videos]
    log_callback(f"Selecionados {len(selected_videos)} vídeos para processar", "info")

    if max_duration > 0:
        log_callback(f"Tempo máximo configurado: {max_duration}s", "info")

    concat_list_path = Path("./concat_list.txt")
    temp_video_files = []

    total_videos = len(selected_videos)
    progress_step = 90 / total_videos

    log_callback(f"Processando {total_videos} vídeos...", "info")

    with open(concat_list_path, "w", encoding="utf-8") as f_concat:
        for i, vid_file in enumerate(selected_videos):
            temp_output = Path(f"./temp_clip_{i}.ts")
            temp_video_files.append(temp_output)

            log_callback(f"  [{i + 1}/{total_videos}] Processando: {vid_file.name}", "debug")

            # Detecta a duração do vídeo para aplicar fade corretamente
            video_duration = get_video_duration(vid_file, ffmpeg_path)

            # Ajusta a duração se velocidade for diferente de 1.0
            adjusted_duration = video_duration
            if video_duration and video_speed != 1.0:
                adjusted_duration = video_duration / video_speed

            # Filtro de vídeo com velocidade e fade
            vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"

            # Aplica filtro de velocidade se diferente de 1.0
            if video_speed != 1.0:
                # setpts ajusta o timestamp do vídeo para mudar velocidade
                # Fórmula: setpts=(1/velocidade)*PTS
                pts_multiplier = 1.0 / video_speed
                vf += f"setpts={pts_multiplier}*PTS,"
                log_callback(f"    Aplicando velocidade {video_speed}x (PTS: {pts_multiplier})", "debug")

            # Adiciona fade apenas se ativado
            if fade_enabled and fade_duration > 0 and adjusted_duration:
                # Calcula quando o fade out deve começar (duração ajustada - tempo do fade)
                fade_out_start = max(0, adjusted_duration - fade_duration)
                vf += f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={fade_out_start}:d={fade_duration},"
                log_callback(
                    f"    Duração: {video_duration:.2f}s → {adjusted_duration:.2f}s, Fade out em: {fade_out_start:.2f}s",
                    "debug")
            elif fade_enabled and fade_duration > 0:
                # Se não conseguir detectar duração, aplica apenas fade in
                vf += f"fade=t=in:st=0:d={fade_duration},"
                log_callback(f"    Duração não detectada, usando apenas fade in", "debug")

            vf += "format=yuv420p"

            # Prepara filtro de áudio para velocidade
            af = ""
            if video_speed != 1.0:
                # atempo tem limite de 0.5 a 2.0, então precisa encadear se necessário
                tempo = video_speed
                atempo_filters = []

                # Se velocidade > 2.0, divide em múltiplos filtros
                while tempo > 2.0:
                    atempo_filters.append("atempo=2.0")
                    tempo = tempo / 2.0

                # Se velocidade < 0.5, divide em múltiplos filtros
                while tempo < 0.5:
                    atempo_filters.append("atempo=0.5")
                    tempo = tempo / 0.5

                # Adiciona o resto
                if tempo != 1.0:
                    atempo_filters.append(f"atempo={tempo}")

                af = ",".join(atempo_filters)
                log_callback(f"    Filtros de áudio: {af}", "debug")

            cmd = [
                ffmpeg_path, "-y", "-i", str(vid_file),
                "-vf", vf
            ]

            # Adiciona filtro de áudio se houver mudança de velocidade
            if af:
                cmd.extend(["-af", af])

            cmd.extend([
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-r", "30",
                "-c:a", "aac", "-b:a", "192k",
                str(temp_output)
            ])

            # Log do comando (apenas em caso de erro vamos mostrar)
            cmd_str = ' '.join(str(c) for c in cmd)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                log_callback(f"AVISO: Erro ao processar {vid_file.name}", "warning")
                log_callback(f"  Código de erro: {result.returncode}", "debug")
                log_callback(f"  Comando executado: {cmd_str}", "debug")
                # Mostra mais detalhes do erro - últimas linhas do stderr
                error_lines = result.stderr.strip().split('\n')
                relevant_errors = error_lines[-10:] if len(error_lines) > 10 else error_lines
                for line in relevant_errors:
                    if line.strip():
                        log_callback(f"  {line}", "debug")

            f_concat.write(f"file '{temp_output.resolve()}'\n")
            progress_callback(int((i + 1) * progress_step))

    log_callback("Concatenando vídeos...", "info")

    # Comando final para concatenar
    final_cmd = [
        ffmpeg_path, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path), "-c", "copy"
    ]

    if max_duration > 0:
        final_cmd.extend(["-t", str(max_duration)])

    final_cmd.append(str(output_path))

    final_cmd_str = ' '.join(str(c) for c in final_cmd)

    result = subprocess.run(final_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log_callback(f"ERRO na concatenação final!", "error")
        log_callback(f"Código de erro: {result.returncode}", "error")
        log_callback(f"Comando: {final_cmd_str}", "debug")
        # Mostra as últimas linhas de erro que são mais relevantes
        error_lines = result.stderr.strip().split('\n')
        relevant_errors = error_lines[-15:] if len(error_lines) > 15 else error_lines
        for line in relevant_errors:
            if line.strip():
                log_callback(f"  {line}", "error")
    else:
        log_callback("✓ Vídeo criado com sucesso!", "success")

    progress_callback(100)

    # Limpeza
    log_callback("Limpando arquivos temporários...", "debug")
    for temp_file in temp_video_files:
        if temp_file.exists():
            os.remove(temp_file)
    if concat_list_path.exists():
        os.remove(concat_list_path)
    log_callback("Limpeza concluída", "debug")


# --- Interface Gráfica (GUI) ---

class VideoCreatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Criador de Vídeos Avançado")
        self.geometry("600x920")

        # Variáveis de estado
        self.mode = tk.StringVar(value="images")
        self.folder_path = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.image_duration = tk.StringVar(value="5")
        self.video_count = tk.StringVar(value="10")
        self.video_speed = tk.StringVar(value="1.0")
        self.max_duration = tk.StringVar(value="0")
        self.num_videos_to_create = tk.StringVar(value="1")
        self.ken_burns = tk.BooleanVar(value=True)
        self.sequential = tk.BooleanVar(value=False)
        self.direct_concat = tk.BooleanVar(value=True)

        # Novas variáveis para qualidade e efeitos
        self.crf_value = tk.IntVar(value=27)
        self.preset_value = tk.StringVar(value="fast")
        self.fade_enabled = tk.BooleanVar(value=True)
        self.fade_duration = tk.DoubleVar(value=0.5)

        # Estilo
        style = ttk.Style(self)
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0")
        style.configure("TRadiobutton", background="#f0f0f0")
        style.configure("TCheckbutton", background="#f0f0f0")

        # Frame principal
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill="both", expand=True)

        # 1. Seleção de Modo
        mode_frame = ttk.LabelFrame(main_frame, text="1. Escolha o Modo")
        mode_frame.pack(fill="x", pady=5)
        ttk.Radiobutton(mode_frame, text="Criar a partir de Imagens", variable=self.mode, value="images",
                        command=self.update_ui).pack(anchor="w", padx=10)
        ttk.Radiobutton(mode_frame, text="Criar a partir de Vídeos", variable=self.mode, value="videos",
                        command=self.update_ui).pack(anchor="w", padx=10)

        # 2. Seleção de Pasta de Entrada
        folder_frame = ttk.LabelFrame(main_frame, text="2. Pasta de Entrada (Mídia)")
        folder_frame.pack(fill="x", pady=5)

        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_path, state="readonly", width=40)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        browse_button = ttk.Button(folder_frame, text="Procurar...", command=self.browse_folder)
        browse_button.pack(side="right", padx=5)

        # 3. Seleção de Pasta de Saída
        output_frame = ttk.LabelFrame(main_frame, text="3. Pasta de Saída")
        output_frame.pack(fill="x", pady=5)

        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_folder, state="readonly", width=40)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        output_browse_button = ttk.Button(output_frame, text="Procurar...", command=self.browse_output_folder)
        output_browse_button.pack(side="right", padx=5)

        # 4. Quantidade de vídeos
        num_videos_frame = ttk.LabelFrame(main_frame, text="4. Quantidade de Vídeos")
        num_videos_frame.pack(fill="x", pady=5)

        num_container = ttk.Frame(num_videos_frame)
        num_container.pack(fill="x", padx=10, pady=5)
        ttk.Label(num_container, text="Quantos vídeos criar com estes assets:").pack(side="left", padx=5)
        self.num_videos_entry = ttk.Entry(num_container, textvariable=self.num_videos_to_create, width=5)
        self.num_videos_entry.pack(side="left")
        ttk.Label(num_container, text="(cada vídeo terá uma combinação diferente)").pack(side="left", padx=5)

        # 5. Tempo limite
        duration_limit_frame = ttk.LabelFrame(main_frame, text="5. Duração Máxima do Vídeo")
        duration_limit_frame.pack(fill="x", pady=5)

        duration_container = ttk.Frame(duration_limit_frame)
        duration_container.pack(fill="x", padx=10, pady=5)
        ttk.Label(duration_container, text="Tempo máximo do vídeo (segundos):").pack(side="left", padx=5)
        self.max_duration_entry = ttk.Entry(duration_container, textvariable=self.max_duration, width=8)
        self.max_duration_entry.pack(side="left")
        ttk.Label(duration_container, text="(0 = sem limite)").pack(side="left", padx=5)

        # 6. Opções Específicas do Modo
        self.options_frame = ttk.LabelFrame(main_frame, text="6. Opções do Modo")
        self.options_frame.pack(fill="x", pady=5)

        # --- Campos para Imagens ---
        self.image_options_frame = ttk.Frame(self.options_frame)
        ttk.Label(self.image_options_frame, text="Tempo por imagem (segundos):").pack(side="left", padx=5)
        self.image_duration_entry = ttk.Entry(self.image_options_frame, textvariable=self.image_duration, width=5)
        self.image_duration_entry.pack(side="left")

        # --- Campos para Vídeos ---
        self.video_options_frame = ttk.Frame(self.options_frame)

        video_count_container = ttk.Frame(self.video_options_frame)
        video_count_container.pack(fill="x", pady=2)
        ttk.Label(video_count_container, text="Quantidade de vídeos a usar:").pack(side="left", padx=5)
        self.video_count_entry = ttk.Entry(video_count_container, textvariable=self.video_count, width=5)
        self.video_count_entry.pack(side="left")

        video_speed_container = ttk.Frame(self.video_options_frame)
        video_speed_container.pack(fill="x", pady=2)
        ttk.Label(video_speed_container, text="Velocidade dos vídeos:").pack(side="left", padx=5)
        self.video_speed_entry = ttk.Entry(video_speed_container, textvariable=self.video_speed, width=8)
        self.video_speed_entry.pack(side="left")
        self.video_speed_entry.bind('<KeyRelease>', lambda e: self.update_concat_warning())
        ttk.Label(video_speed_container, text="(0.5=mais lento, 1.0=normal, 2.0=mais rápido)").pack(side="left", padx=5)

        # Opção de concatenação direta
        video_concat_container = ttk.Frame(self.video_options_frame)
        video_concat_container.pack(fill="x", pady=5)
        self.direct_concat_check = ttk.Checkbutton(
            video_concat_container,
            text="⚡ Concatenação Direta (sem recodificação - muito mais rápido)",
            variable=self.direct_concat,
            command=self.update_concat_warning
        )
        self.direct_concat_check.pack(anchor="w", padx=5)

        self.concat_warning_label = ttk.Label(
            video_concat_container,
            text="",
            foreground="orange",
            font=("TkDefaultFont", 8)
        )
        self.concat_warning_label.pack(anchor="w", padx=20)

        # 7. Qualidade e Velocidade
        quality_frame = ttk.LabelFrame(main_frame, text="7. Qualidade e Velocidade")
        quality_frame.pack(fill="x", pady=5)

        # CRF
        crf_container = ttk.Frame(quality_frame)
        crf_container.pack(fill="x", padx=10, pady=5)
        self.crf_label = ttk.Label(crf_container, text=f"Qualidade (CRF) Padrão: 27 (18=Melhor)")
        self.crf_label.pack(anchor="w")
        self.crf_slider = ttk.Scale(crf_container, from_=18, to=35, variable=self.crf_value,
                                    orient="horizontal", command=self.update_crf_label)
        self.crf_slider.pack(fill="x")

        # Preset
        preset_container = ttk.Frame(quality_frame)
        preset_container.pack(fill="x", padx=10, pady=5)
        ttk.Label(preset_container, text="Velocidade (Preset) Padrão:").pack(side="left", padx=(0, 5))
        preset_combo = ttk.Combobox(preset_container, textvariable=self.preset_value,
                                    values=["ultrafast", "superfast", "veryfast", "faster", "fast",
                                            "medium", "slow", "slower", "veryslow"],
                                    state="readonly", width=15)
        preset_combo.pack(side="left")

        # 8. Duração do Fade
        fade_frame = ttk.LabelFrame(main_frame, text="8. Efeito de Transição")
        fade_frame.pack(fill="x", pady=5)

        # Toggle para ativar/desativar fade
        fade_toggle_container = ttk.Frame(fade_frame)
        fade_toggle_container.pack(fill="x", padx=10, pady=5)
        self.fade_check = ttk.Checkbutton(
            fade_toggle_container,
            text="Ativar efeito de Fade (transição suave)",
            variable=self.fade_enabled,
            command=self.update_fade_ui
        )
        self.fade_check.pack(anchor="w")

        fade_container = ttk.Frame(fade_frame)
        fade_container.pack(fill="x", padx=10, pady=5)
        self.fade_label = ttk.Label(fade_container, text=f"Duração do Fade (Segundos): 0.5s")
        self.fade_label.pack(anchor="w")
        self.fade_slider = ttk.Scale(fade_container, from_=0.1, to=2, variable=self.fade_duration,
                                     orient="horizontal", command=self.update_fade_label)
        self.fade_slider.pack(fill="x")

        # 9. Opções Gerais
        general_options_frame = ttk.LabelFrame(main_frame, text="9. Opções Gerais")
        general_options_frame.pack(fill="x", pady=5, ipady=5)

        self.ken_burns_check = ttk.Checkbutton(general_options_frame, text="Habilitar efeito Ken Burns (movimento)",
                                               variable=self.ken_burns)
        self.ken_burns_check.pack(anchor="w", padx=10)

        self.sequential_check = ttk.Checkbutton(general_options_frame, text="Usar ordem sequencial (por nome)",
                                                variable=self.sequential)
        self.sequential_check.pack(anchor="w", padx=10)

        # 10. Ação
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=15)

        self.create_button = ttk.Button(action_frame, text="Criar Vídeo(s)", command=self.start_creation)
        self.create_button.pack(pady=5)

        self.progress_bar = ttk.Progressbar(action_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(pady=5)

        self.status_label = ttk.Label(action_frame, text="Pronto para processar", foreground="blue")
        self.status_label.pack(pady=2)

        # 11. Área de Logs
        log_frame = ttk.LabelFrame(main_frame, text="Logs do Processo")
        log_frame.pack(fill="both", expand=True, pady=10)

        # Frame para botões de controle de log
        log_controls = ttk.Frame(log_frame)
        log_controls.pack(fill="x", padx=5, pady=5)

        clear_log_btn = ttk.Button(log_controls, text="Limpar Logs", command=self.clear_logs)
        clear_log_btn.pack(side="right")

        # Scrollbar e Text widget para logs
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side="right", fill="y")

        self.log_text = tk.Text(log_frame, height=8, wrap="word", yscrollcommand=log_scroll.set,
                                bg="#1e1e1e", fg="#ffffff", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        log_scroll.config(command=self.log_text.yview)

        # Configurar tags de cor
        self.log_text.tag_config("info", foreground="#00d4ff")
        self.log_text.tag_config("success", foreground="#00ff00")
        self.log_text.tag_config("warning", foreground="#ffaa00")
        self.log_text.tag_config("error", foreground="#ff0000")
        self.log_text.tag_config("debug", foreground="#888888")

        # Inicializa a UI
        self.update_ui()
        self.update_fade_ui()
        self.update_concat_warning()
        self.log("Sistema iniciado. Aguardando entrada...", "info")

    def clear_logs(self):
        """Limpa a área de logs."""
        self.log_text.delete(1.0, "end")
        self.log("Logs limpos.", "info")

    def update_fade_ui(self):
        """Atualiza a interface de fade baseado no estado do checkbox."""
        if self.fade_enabled.get():
            self.fade_slider.config(state="normal")
            self.fade_label.config(foreground="black")
        else:
            self.fade_slider.config(state="disabled")
            self.fade_label.config(foreground="gray")

        # Atualiza aviso de concatenação direta
        if hasattr(self, 'concat_warning_label'):
            self.update_concat_warning()

    def update_concat_warning(self):
        """Atualiza o aviso sobre concatenação direta."""
        if self.mode.get() != "videos":
            return

        # Verifica se pode usar concatenação direta
        try:
            speed = float(self.video_speed.get())
        except:
            speed = 1.0

        fade_active = self.fade_enabled.get()
        speed_changed = speed != 1.0

        # Desabilita concatenação direta se necessário
        if (fade_active or speed_changed) and self.direct_concat.get():
            self.direct_concat.set(False)
            self.direct_concat_check.config(state="disabled")

            reasons = []
            if fade_active:
                reasons.append("fade ativado")
            if speed_changed:
                reasons.append(f"velocidade alterada ({speed}x)")

            warning = f"⚠ Desabilitado: {' e '.join(reasons)}"
            self.concat_warning_label.config(text=warning)
        else:
            self.direct_concat_check.config(state="normal")
            if self.direct_concat.get():
                self.concat_warning_label.config(
                    text="✓ Melhor resultado com vídeos do mesmo formato/codec",
                    foreground="green"
                )
            else:
                self.concat_warning_label.config(text="")

    def log(self, message, level="info"):
        """Adiciona uma mensagem ao log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert("end", log_message, level)
        self.log_text.see("end")
        self.update_idletasks()

    def update_crf_label(self, value):
        """Atualiza o label do CRF."""
        crf = int(float(value))
        quality = "Melhor" if crf <= 20 else "Boa" if crf <= 25 else "Média" if crf <= 30 else "Baixa"
        self.crf_label.config(text=f"Qualidade (CRF) Padrão: {crf} ({quality})")

    def update_fade_label(self, value):
        """Atualiza o label do Fade."""
        fade = float(value)
        self.fade_label.config(text=f"Duração do Fade Padrão (Segundos): {fade:.1f}s")

    def update_ui(self):
        """Atualiza a interface com base no modo selecionado."""
        mode = self.mode.get()
        if mode == "images":
            self.video_options_frame.pack_forget()
            self.image_options_frame.pack(pady=10)
            self.ken_burns_check.config(state="normal")
        else:
            self.image_options_frame.pack_forget()
            self.video_options_frame.pack(pady=10)
            self.ken_burns_check.config(state="disabled")

    def browse_folder(self):
        """Abre o diálogo para selecionar uma pasta de entrada."""
        path = filedialog.askdirectory(title="Selecione a pasta com as mídias")
        if path:
            self.folder_path.set(path)

    def browse_output_folder(self):
        """Abre o diálogo para selecionar uma pasta de saída."""
        path = filedialog.askdirectory(title="Selecione a pasta de saída")
        if path:
            self.output_folder.set(path)

    def update_progress(self, value):
        """Atualiza a barra de progresso."""
        self.progress_bar['value'] = value
        self.update_idletasks()

    def update_status(self, text, color="blue"):
        """Atualiza o status da aplicação."""
        self.status_label.config(text=text, foreground=color)
        self.update_idletasks()

    def start_creation(self):
        """Valida os inputs e inicia o processo de criação do vídeo."""
        folder = self.folder_path.get()
        output_folder = self.output_folder.get()

        # Limpa logs anteriores
        self.log_text.delete(1.0, "end")

        self.log("=" * 50, "info")
        self.log("INICIANDO PROCESSO DE CRIAÇÃO", "info")
        self.log("=" * 50, "info")

        if not folder:
            self.log("ERRO: Pasta de entrada não selecionada", "error")
            messagebox.showwarning("Aviso", "Por favor, selecione uma pasta de entrada primeiro.")
            return

        self.log(f"Pasta de entrada: {folder}", "debug")

        if not output_folder:
            self.log("ERRO: Pasta de saída não selecionada", "error")
            messagebox.showwarning("Aviso", "Por favor, selecione uma pasta de saída primeiro.")
            return

        self.log(f"Pasta de saída: {output_folder}", "debug")

        self.create_button.config(state="disabled")
        self.update_progress(0)

        try:
            num_videos = int(self.num_videos_to_create.get())
            if num_videos < 1:
                raise ValueError("O número de vídeos deve ser maior que 0")

            # Valida velocidade se for modo vídeos
            if self.mode.get() == "videos":
                speed = float(self.video_speed.get())
                if speed <= 0 or speed > 10:
                    raise ValueError("A velocidade deve estar entre 0.1 e 10.0")

            self.log(f"Número de vídeos a criar: {num_videos}", "info")
            self.log(f"Modo selecionado: {self.mode.get()}", "info")

            self.process_multiple_videos(num_videos)

        except ValueError as e:
            self.log(f"ERRO DE VALIDAÇÃO: {e}", "error")
            messagebox.showerror("Erro", f"Valor inválido: {e}")
        except Exception as e:
            self.log(f"ERRO INESPERADO: {e}", "error")
            import traceback
            self.log(f"Traceback:\n{traceback.format_exc()}", "error")
            messagebox.showerror("Erro Inesperado", f"Ocorreu um erro: {e}")
        finally:
            self.create_button.config(state="normal")
            self.update_progress(0)
            self.log("=" * 50, "info")
            self.log("PROCESSO FINALIZADO", "info")
            self.log("=" * 50, "info")

    def process_multiple_videos(self, num_videos):
        """Processa múltiplos vídeos a partir da mesma pasta."""
        folder = self.folder_path.get()
        output_folder = self.output_folder.get()
        folder_name = Path(folder).name

        # Obtém o tempo máximo
        max_duration = float(self.max_duration.get())

        self.log(f"Configurações:", "info")
        self.log(f"  - Duração máxima: {max_duration}s (0 = sem limite)", "info")
        self.log(f"  - CRF: {self.crf_value.get()}", "info")
        self.log(f"  - Preset: {self.preset_value.get()}", "info")
        self.log(f"  - Fade: {'Ativado' if self.fade_enabled.get() else 'Desativado'} ({self.fade_duration.get()}s)",
                 "info")
        self.log(f"  - Ken Burns: {'Sim' if self.ken_burns.get() else 'Não'}", "info")
        self.log(f"  - Sequencial: {'Sim' if self.sequential.get() else 'Não'}", "info")

        if self.mode.get() == "videos":
            speed = float(self.video_speed.get())
            self.log(f"  - Velocidade dos vídeos: {speed}x", "info")
            use_direct = self.direct_concat.get()
            self.log(f"  - Concatenação: {'⚡ Direta (sem recodificação)' if use_direct else '🔄 Com recodificação'}",
                     "info")

        successful = 0
        failed = 0

        for video_num in range(1, num_videos + 1):
            try:
                self.log("", "info")
                self.log(f"--- VÍDEO {video_num}/{num_videos} ---", "info")

                # Gera nome de arquivo único
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"video_{folder_name}_{video_num}_{timestamp}.mp4"
                output_path = str(Path(output_folder) / output_filename)

                self.log(f"Arquivo de saída: {output_filename}", "info")
                self.update_status(f"Criando vídeo {video_num}/{num_videos}: {output_filename}", "orange")

                if self.mode.get() == "images":
                    duration = float(self.image_duration.get())
                    self.log(f"Modo: Imagens (duração por imagem: {duration}s)", "info")
                    create_video_from_images(
                        folder, output_path, duration,
                        self.ken_burns.get(), self.sequential.get(),
                        self.crf_value.get(), self.preset_value.get(),
                        self.fade_enabled.get(), self.fade_duration.get(), max_duration,
                        self.update_progress, self.log
                    )
                else:
                    count = int(self.video_count.get())
                    speed = float(self.video_speed.get())
                    use_direct = self.direct_concat.get()

                    if use_direct:
                        self.log(f"Modo: Vídeos - Concatenação Direta (quantidade: {count})", "info")
                        self.log(f"⚡ Processamento rápido sem recodificação", "info")
                        create_video_from_videos_direct(
                            folder, output_path, count, self.sequential.get(),
                            max_duration,
                            self.update_progress, self.log
                        )
                    else:
                        self.log(f"Modo: Vídeos - Com Recodificação (quantidade: {count}, velocidade: {speed}x)",
                                 "info")
                        create_video_from_videos(
                            folder, output_path, count, self.sequential.get(),
                            self.crf_value.get(), self.preset_value.get(),
                            self.fade_enabled.get(), self.fade_duration.get(), max_duration, speed,
                            self.update_progress, self.log
                        )

                successful += 1
                self.log(f"✓ Vídeo {video_num} criado com sucesso!", "success")
                self.update_status(f"✓ Vídeo {video_num}/{num_videos} concluído!", "green")

            except Exception as e:
                failed += 1
                self.log(f"✗ ERRO ao criar vídeo {video_num}: {e}", "error")
                import traceback
                self.log(f"Detalhes do erro:\n{traceback.format_exc()}", "error")
                self.update_status(f"✗ Erro no vídeo {video_num}/{num_videos}", "red")

        # Mensagem final
        self.log("", "info")
        self.log("=" * 50, "info")
        self.log(f"RESUMO FINAL", "info")
        self.log(f"  Total de vídeos solicitados: {num_videos}", "info")
        self.log(f"  Criados com sucesso: {successful}", "success" if successful > 0 else "info")
        self.log(f"  Falhas: {failed}", "error" if failed > 0 else "info")
        self.log("=" * 50, "info")

        self.update_status(
            f"✓ Processo concluído: {successful} sucesso(s), {failed} falha(s)",
            "green" if failed == 0 else "orange"
        )

        if successful > 0:
            messagebox.showinfo(
                "Processo Concluído",
                f"Vídeos criados: {successful}/{num_videos}\n"
                f"Falhas: {failed}\n"
                f"Pasta de saída: {output_folder}"
            )
        else:
            messagebox.showerror(
                "Erro no Processamento",
                f"Não foi possível criar nenhum vídeo.\n"
                f"Verifique os logs para mais detalhes."
            )


if __name__ == "__main__":
    get_ffmpeg_path()
    app = VideoCreatorApp()
    app.mainloop()