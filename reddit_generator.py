import sys
import os
import json
import re

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                 QHBoxLayout, QLabel, QLineEdit, QPushButton,
                                 QTextEdit, QComboBox, QFileDialog, QMessageBox,
                                 QProgressBar, QGroupBox)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QFont, QPalette, QColor

    Signal = pyqtSignal
    print("✅ Usando PyQt6")
except ImportError:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                   QHBoxLayout, QLabel, QLineEdit, QPushButton,
                                   QTextEdit, QComboBox, QFileDialog, QMessageBox,
                                   QProgressBar, QGroupBox)
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QFont, QPalette, QColor

    print("✅ Usando PySide6")

from docx import Document
from docx.shared import Pt
import openai
from datetime import datetime


class GeneratorThread(QThread):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, api_key, prompt_completo, titulos_formatos, pasta_saida):
        super().__init__()
        self.api_key = api_key
        self.prompt_completo = prompt_completo
        self.titulos_formatos = titulos_formatos
        self.pasta_saida = pasta_saida
        self.running = True

    def stop(self):
        self.running = False

    def limpar_formatacao(self, texto):
        """Remove formatação markdown e estruturas desnecessárias"""
        texto = re.sub(r'^#+\s+.*$', '', texto, flags=re.MULTILINE)
        texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)
        texto = re.sub(r'\*(.+?)\*', r'\1', texto)
        texto = re.sub(r'__(.+?)__', r'\1', texto)
        texto = re.sub(r'_(.+?)_', r'\1', texto)
        texto = re.sub(r'^\s*[-*+]\s+', '', texto, flags=re.MULTILINE)
        texto = re.sub(r'^\s*\d+\.\s+', '', texto, flags=re.MULTILINE)
        texto = re.sub(r'\n{3,}', '\n\n', texto)
        return texto.strip()

    def gerar_roteiro_short_e_longo(self, client, titulo):
        """Gera SHORT e VÍDEO LONGO em duas chamadas separadas"""
        self.progress.emit(f"\n{'=' * 70}")
        self.progress.emit(f"🎬 Gerando: {titulo}")
        self.progress.emit(f"📋 Formato: Short + Vídeo Longo (2 gerações)")
        self.progress.emit(f"{'=' * 70}\n")

        # GERAR SHORT
        self.progress.emit("📱 ETAPA 1/2: Gerando SHORT...")

        prompt_short = f"""{self.prompt_completo}

---

## Formato: SHORT

Você deve gerar APENAS o SHORT (versão curta):
- Máximo de 720 palavras
- Início da história com gancho potente
- Termina com suspense/curiosidade
- Narrativa corrida em primeira pessoa
- Português do Brasil

## Tarefa

Título: "{titulo}"

Crie APENAS o roteiro SHORT (720 palavras). Este será o INÍCIO EXATO do vídeo longo.
NÃO gere o vídeo longo ainda.
"""

        try:
            response_short = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system",
                     "content": "Você é um especialista em criar roteiros SHORT de storytelling adulto dramático em português brasileiro. Você cria versões curtas e impactantes de 400 palavras."},
                    {"role": "user", "content": prompt_short}
                ],
                temperature=0.85,
                max_tokens=2000
            )

            roteiro_short = response_short.choices[0].message.content
            roteiro_short_limpo = self.limpar_formatacao(roteiro_short)
            palavras_short = len(roteiro_short_limpo.split())

            self.progress.emit(f"   ✅ Short gerado: {palavras_short} palavras\n")

        except Exception as e:
            raise Exception(f"Erro ao gerar SHORT: {str(e)}")

        # GERAR VÍDEO LONGO
        self.progress.emit("🎥 ETAPA 2/2: Gerando VÍDEO LONGO...")

        prompt_longo = f"""{self.prompt_completo}

---

## Formato: VÍDEO LONGO (Continuação EXATA do Short)

### REGRA CRÍTICA - LEIA COM ATENÇÃO:

O vídeo longo NÃO é uma versão diferente da história.
O vídeo longo DEVE começar com o SHORT COMPLETO (palavra por palavra), e depois continuar.

### SHORT COMPLETO (COPIE ESTE TEXTO EXATAMENTE):

{roteiro_short_limpo}

---

### INSTRUÇÕES PARA O VÍDEO LONGO:

**PASSO 1 - COPIAR O SHORT:**
Comece o vídeo longo copiando TODO o texto do short acima, SEM MODIFICAR NADA.
Use EXATAMENTE as mesmas palavras, frases e parágrafos.

**PASSO 2 - CONTINUAR A HISTÓRIA:**
APÓS terminar de copiar o short completo, continue a história naturalmente.
Expanda a narrativa com mais 2500-3000 palavras adicionais.

**ESTRUTURA FINAL DO VÍDEO LONGO:**
1. [SHORT COMPLETO - 720 palavras copiadas]
2. [CONTINUAÇÃO - 2500-3000 palavras novas]
3. [Desfecho completo]
4. [Chamadas para inscrição no meio e no final]

**TOTAL**: 3000-4000 palavras

## Tarefa

Título: "{titulo}"

Gere o VÍDEO LONGO seguindo EXATAMENTE os passos acima.
IMPORTANTE: NÃO reescreva o short. COPIE palavra por palavra e depois CONTINUE.
"""

        try:
            response_longo = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system",
                     "content": "Você é um especialista em criar roteiros LONGOS de storytelling adulto dramático em português brasileiro. Quando receber um SHORT para expandir, você DEVE começar o vídeo longo copiando o SHORT COMPLETO palavra por palavra, e só depois continuar a história. NUNCA reescreva o short, apenas COPIE e CONTINUE."},
                    {"role": "user", "content": prompt_longo}
                ],
                temperature=0.85,
                max_tokens=16000
            )

            roteiro_longo = response_longo.choices[0].message.content
            roteiro_longo_limpo = self.limpar_formatacao(roteiro_longo)
            palavras_longo = len(roteiro_longo_limpo.split())

            self.progress.emit(f"   ✅ Vídeo Longo gerado: {palavras_longo} palavras")

            # VALIDAÇÃO: Verificar se o vídeo longo começa com o short
            primeiras_100_palavras_short = ' '.join(roteiro_short_limpo.split()[:100])
            primeiras_100_palavras_longo = ' '.join(roteiro_longo_limpo.split()[:100])

            similaridade = sum(1 for a, b in zip(primeiras_100_palavras_short.split(),
                                                 primeiras_100_palavras_longo.split()) if a == b)
            percentual = (similaridade / 100) * 100

            if percentual < 80:
                self.progress.emit(f"   ⚠️ AVISO: Vídeo longo pode não ter copiado o short corretamente")
                self.progress.emit(f"   Similaridade: {percentual:.0f}% (esperado: >80%)")
            else:
                self.progress.emit(f"   ✅ Validação: Short copiado corretamente ({percentual:.0f}% de similaridade)")

            self.progress.emit("")

        except Exception as e:
            raise Exception(f"Erro ao gerar VÍDEO LONGO: {str(e)}")

        # COMBINAR OS DOIS
        # Como o vídeo longo já inclui o short no início, usamos apenas ele
        # Mas adicionamos um marcador para facilitar identificação
        roteiro_completo = f"""[VERSÃO SHORT - 720 palavras]

{roteiro_short_limpo}

{'=' * 70}

[VERSÃO COMPLETA - VÍDEO LONGO]

{roteiro_longo_limpo}"""

        palavras_total = palavras_short + palavras_longo
        self.progress.emit(
            f"✅ Roteiro combinado: Short ({palavras_short} palavras) + Vídeo Longo ({palavras_longo} palavras)\n")

        return roteiro_completo

    def gerar_roteiro(self, client, titulo, formato):
        """Gera o roteiro completo baseado no formato"""
        self.progress.emit(f"\n{'=' * 70}")
        self.progress.emit(f"🎬 Gerando roteiro: {titulo}")
        self.progress.emit(f"📋 Formato: {formato}")
        self.progress.emit(f"{'=' * 70}\n")

        # Construir prompt específico para o formato
        if formato.lower() == "short":
            instrucao_formato = """
### 1. Short (até 2:30)

- Roteiro curto, fechado e direto, terminando com um clímax claro ou uma micro-reviravolta.
- Texto deve ter, no máximo, 720 palavras e foco no conflito principal e sua resolução.
- O roteiro deve ser totalmente independente, mas estimular curiosidade para mais histórias do canal.
"""
            max_tokens = 2000
            temperatura = 0.85
        else:  # vídeo longo
            instrucao_formato = """
### 2. Vídeo longo (até 23 minutos)

- Roteiro detalhado, dividido em até 4 blocos de até 1000 palavras cada, cobrindo toda a trajetória da história, personagens, suspense, reviravoltas e desfecho completo.
- Realize chamadas para inscrição e comentários no final do segundo e último bloco, sempre de maneira acolhedora, calorosa e criativa.
"""
            max_tokens = 16000
            temperatura = 0.85

        prompt_final = f"""{self.prompt_completo}

---

## Formato Solicitado

{instrucao_formato}

---

## Tarefa

- Título: "{titulo}"
- Formato: {formato}

Crie o roteiro completo seguindo EXATAMENTE as instruções do formato escolhido.
"""

        self.progress.emit(f"🤖 Gerando roteiro com IA...")
        self.progress.emit(f"⚙️ Parâmetros: max_tokens={max_tokens}, temp={temperatura}\n")

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system",
                     "content": "Você é um especialista em criar roteiros de storytelling adulto dramático em português brasileiro. Você segue EXATAMENTE as instruções fornecidas sobre formato, estrutura e contagem de palavras."},
                    {"role": "user", "content": prompt_final}
                ],
                temperature=temperatura,
                max_tokens=max_tokens
            )

            roteiro = response.choices[0].message.content
            roteiro_limpo = self.limpar_formatacao(roteiro)

            palavras = len(roteiro_limpo.split())
            self.progress.emit(f"✅ Roteiro gerado: {palavras} palavras\n")

            return roteiro_limpo

        except Exception as e:
            raise Exception(f"Erro ao gerar roteiro: {str(e)}")

    def criar_docx(self, titulo, formato, conteudo, pasta_saida):
        """Cria arquivo DOCX com o roteiro"""
        try:
            doc = Document()

            # Título
            titulo_paragrafo = doc.add_heading(f"{titulo} - {formato}", level=1)
            titulo_paragrafo.alignment = 1

            # Data
            data_paragrafo = doc.add_paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            data_paragrafo.alignment = 1

            doc.add_paragraph()

            # Conteúdo
            paragrafos = conteudo.split('\n\n')
            for paragrafo in paragrafos:
                if paragrafo.strip():
                    p = doc.add_paragraph(paragrafo.strip())
                    p_format = p.paragraph_format
                    p_format.line_spacing = 1.5
                    p_format.space_after = Pt(12)

                    for run in p.runs:
                        run.font.name = 'Arial'
                        run.font.size = Pt(12)

            # Nome do arquivo
            nome_arquivo = re.sub(r'[<>:"/\\|?*]', '', titulo)
            nome_arquivo = f"{nome_arquivo}_{formato.replace(' ', '_')}.docx"
            caminho_completo = os.path.join(pasta_saida, nome_arquivo)

            doc.save(caminho_completo)
            self.progress.emit(f"💾 Arquivo salvo: {nome_arquivo}\n")

        except Exception as e:
            raise Exception(f"Erro ao criar DOCX: {str(e)}")

    def run(self):
        try:
            client = openai.OpenAI(api_key=self.api_key)

            total = len(self.titulos_formatos)
            self.progress.emit(f"🚀 Iniciando geração de {total} roteiro(s)...\n")

            for idx, (titulo, formato) in enumerate(self.titulos_formatos, 1):
                if not self.running:
                    self.progress.emit("⛔ Processo interrompido pelo usuário.")
                    break

                self.progress.emit(f"\n📊 Progresso: {idx}/{total}")

                try:
                    # Se for short + vídeo longo, usa método especial com 2 chamadas
                    if "+" in formato.lower():
                        roteiro = self.gerar_roteiro_short_e_longo(client, titulo)
                    else:
                        roteiro = self.gerar_roteiro(client, titulo, formato)

                    self.criar_docx(titulo, formato, roteiro, self.pasta_saida)

                except Exception as e:
                    self.progress.emit(f"❌ Erro ao processar '{titulo}': {str(e)}\n")
                    continue

            if self.running:
                self.progress.emit(f"\n{'=' * 70}")
                self.progress.emit("✨ PROCESSO CONCLUÍDO COM SUCESSO! ✨")
                self.progress.emit(f"{'=' * 70}\n")
                self.progress.emit(f"📁 Arquivos salvos em: {self.pasta_saida}")
                self.finished.emit()

        except Exception as e:
            self.error.emit(f"❌ Erro crítico: {str(e)}")


class StorytellingGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Roteiros - Storytelling Adulto Dramático v3 (Duas Chamadas)")
        self.setGeometry(100, 100, 1200, 800)

        self.config_file = "config_storytelling.json"
        self.api_key_saved = ""
        self.generator_thread = None

        self.init_ui()
        self.load_config()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("🎭 Gerador de Roteiros - Storytelling v3 (Duas Chamadas)")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        version_label = QLabel("✨ Versão 3: Short + Vídeo Longo são gerados em 2 chamadas separadas à IA")
        version_label.setStyleSheet("color: #27ae60; font-style: italic; font-size: 11px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(version_label)

        # API Key
        api_group = QGroupBox("🔑 Chave API OpenAI")
        api_layout = QVBoxLayout()

        api_row = QHBoxLayout()
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Cole sua chave API aqui (sk-...)")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_row.addWidget(self.api_input)

        self.api_status = QLabel("❌ Não salva")
        self.api_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        api_row.addWidget(self.api_status)

        save_api_btn = QPushButton("💾 Salvar API")
        save_api_btn.clicked.connect(self.save_api_key)
        save_api_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 8px;")
        api_row.addWidget(save_api_btn)

        clear_api_btn = QPushButton("🗑️ Limpar")
        clear_api_btn.clicked.connect(self.clear_api_key)
        clear_api_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")
        api_row.addWidget(clear_api_btn)

        api_layout.addLayout(api_row)
        api_group.setLayout(api_layout)
        main_layout.addWidget(api_group)

        # Arquivos
        files_group = QGroupBox("📁 Configuração de Arquivos")
        files_layout = QVBoxLayout()

        # Títulos
        titulos_row = QHBoxLayout()
        titulos_row.addWidget(QLabel("Arquivo de Títulos:"))
        self.titulos_input = QLineEdit()
        self.titulos_input.setPlaceholderText("Selecione o arquivo .txt com os títulos e formatos")
        titulos_row.addWidget(self.titulos_input)
        titulos_btn = QPushButton("📝 Selecionar")
        titulos_btn.clicked.connect(self.select_titulos)
        titulos_row.addWidget(titulos_btn)
        files_layout.addLayout(titulos_row)

        # Pasta de saída
        saida_row = QHBoxLayout()
        saida_row.addWidget(QLabel("Pasta de Saída:"))
        self.saida_input = QLineEdit()
        self.saida_input.setPlaceholderText("Onde os roteiros serão salvos")
        saida_row.addWidget(self.saida_input)
        saida_btn = QPushButton("📂 Selecionar")
        saida_btn.clicked.connect(self.select_saida)
        saida_row.addWidget(saida_btn)
        files_layout.addLayout(saida_row)

        files_group.setLayout(files_layout)
        main_layout.addWidget(files_group)

        # Prompt
        prompt_group = QGroupBox("📝 Prompt Base")
        prompt_layout = QVBoxLayout()

        prompt_info = QLabel("✏️ Este é o prompt completo que será usado para gerar os roteiros:")
        prompt_info.setStyleSheet("color: #3498db; font-style: italic;")
        prompt_layout.addWidget(prompt_info)

        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Cole aqui o prompt completo de storytelling adulto dramático...")
        self.prompt_text.setMinimumHeight(200)
        prompt_layout.addWidget(self.prompt_text)

        prompt_group.setLayout(prompt_layout)
        main_layout.addWidget(prompt_group)

        # Botões de ação
        actions_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ INICIAR GERAÇÃO")
        self.start_btn.clicked.connect(self.start_generation)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        actions_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ PARAR")
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        actions_layout.addWidget(self.stop_btn)

        main_layout.addLayout(actions_layout)

        # Log
        log_label = QLabel("📊 Log de Progresso:")
        log_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        self.log_text.setStyleSheet("background-color: #2c3e50; color: #ecf0f1; font-family: 'Courier New';")
        main_layout.addWidget(self.log_text)

        # Info
        info_label = QLabel(
            "ℹ️ Formato: 'Título | Formato' (short, vídeo longo, ou short + vídeo longo). Versão 3 usa DUAS chamadas à IA para garantir ambos os roteiros.")
        info_label.setStyleSheet("color: #95a5a6; font-size: 11px; font-style: italic;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

    def load_config(self):
        """Carrega configurações do arquivo JSON"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                if 'api_key' in config and config['api_key']:
                    self.api_key_saved = config['api_key']
                    self.api_input.setText(self.api_key_saved)
                    self.api_status.setText("✅ Salva")
                    self.api_status.setStyleSheet("color: #27ae60; font-weight: bold;")

                if 'titulos_path' in config and config['titulos_path']:
                    self.titulos_input.setText(config['titulos_path'])

                if 'saida_path' in config and config['saida_path']:
                    self.saida_input.setText(config['saida_path'])

                if 'prompt' in config and config['prompt']:
                    self.prompt_text.setPlainText(config['prompt'])

                self.log_text.append("📁 Configurações anteriores carregadas com sucesso!\n")

        except Exception as e:
            self.log_text.append(f"⚠️ Não foi possível carregar configurações: {str(e)}\n")

    def save_config(self):
        """Salva configurações no arquivo JSON"""
        try:
            config = {
                'api_key': self.api_key_saved,
                'titulos_path': self.titulos_input.text().strip(),
                'saida_path': self.saida_input.text().strip(),
                'prompt': self.prompt_text.toPlainText()
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            return True
        except Exception as e:
            self.log_text.append(f"⚠️ Erro ao salvar configurações: {str(e)}")
            return False

    def clear_api_key(self):
        """Limpa a chave API salva"""
        reply = QMessageBox.question(self, 'Confirmar',
                                     'Tem certeza que deseja limpar a chave API salva?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.api_key_saved = ""
            self.api_input.clear()
            self.api_status.setText("❌ Não salva")
            self.api_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.save_config()
            self.log_text.append("🗑️ Chave API removida com sucesso!\n")
            QMessageBox.information(self, "Sucesso", "Chave API removida!")

    def save_api_key(self):
        api_key = self.api_input.text().strip()
        if api_key:
            self.api_key_saved = api_key
            self.api_status.setText("✅ Salva")
            self.api_status.setStyleSheet("color: #27ae60; font-weight: bold;")

            if self.save_config():
                self.log_text.append("✅ Chave API salva com sucesso!")
                self.log_text.append(f"🔑 Chave: {api_key[:7]}...{api_key[-4:]}")
                self.log_text.append("💾 Configuração salva em 'config_storytelling.json'\n")
                QMessageBox.information(self, "Sucesso",
                                        "Chave API salva com sucesso!\n\nSuas configurações foram salvas localmente.")
            else:
                QMessageBox.warning(self, "Aviso",
                                    "Chave salva na memória, mas houve erro ao salvar no arquivo.")
        else:
            QMessageBox.warning(self, "Aviso", "Por favor, insira uma chave API válida.")

    def select_titulos(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo de Títulos", "",
                                                   "Arquivos de Texto (*.txt)")
        if file_name:
            self.titulos_input.setText(file_name)
            self.log_text.append(f"📝 Arquivo de títulos selecionado: {file_name}")
            self.save_config()

    def select_saida(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Saída")
        if folder:
            self.saida_input.setText(folder)
            self.log_text.append(f"📂 Pasta de saída selecionada: {folder}")
            self.save_config()

    def start_generation(self):
        api_key = self.api_key_saved
        titulos_path = self.titulos_input.text().strip()
        saida_path = self.saida_input.text().strip()
        prompt_texto = self.prompt_text.toPlainText().strip()

        if not api_key:
            QMessageBox.warning(self, "Aviso", "Por favor, insira e salve a chave API primeiro.")
            return

        if not titulos_path or not os.path.exists(titulos_path):
            QMessageBox.warning(self, "Aviso", "Por favor, selecione um arquivo de títulos válido.")
            return

        if not saida_path or not os.path.exists(saida_path):
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma pasta de saída válida.")
            return

        if not prompt_texto:
            QMessageBox.warning(self, "Aviso", "Por favor, insira o prompt base.")
            return

        try:
            with open(titulos_path, 'r', encoding='utf-8') as f:
                linhas = [linha.strip() for linha in f.readlines() if linha.strip()]

            titulos_formatos = []
            for linha in linhas:
                if '|' in linha:
                    partes = linha.split('|')
                    titulo = partes[0].strip()
                    formato = partes[1].strip() if len(partes) > 1 else "vídeo longo"
                else:
                    titulo = linha
                    formato = "vídeo longo"

                titulos_formatos.append((titulo, formato))

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler títulos: {str(e)}")
            return

        if not titulos_formatos:
            QMessageBox.warning(self, "Aviso", "O arquivo de títulos está vazio.")
            return

        self.log_text.clear()
        self.log_text.append("🚀 Iniciando processo de geração...")
        self.log_text.append(f"📊 Total de roteiros a gerar: {len(titulos_formatos)}")
        self.log_text.append("⚡ Versão 3: Short + Vídeo Longo usa 2 chamadas à IA\n")

        for titulo, formato in titulos_formatos:
            self.log_text.append(f"  • {titulo} [{formato}]")

        self.log_text.append("")

        self.generator_thread = GeneratorThread(
            api_key, prompt_texto, titulos_formatos, saida_path
        )
        self.generator_thread.progress.connect(self.update_log)
        self.generator_thread.finished.connect(self.generation_finished)
        self.generator_thread.error.connect(self.generation_error)
        self.generator_thread.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_generation(self):
        if self.generator_thread and self.generator_thread.isRunning():
            self.generator_thread.stop()
            self.log_text.append("\n⏹️ Solicitação de parada enviada...")

    def update_log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def generation_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.information(self, "Concluído", "Processo de geração finalizado!")

    def generation_error(self, error_msg):
        self.log_text.append(f"\n{error_msg}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Erro", error_msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 245))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(33, 33, 33))
    app.setPalette(palette)

    window = StorytellingGenerator()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()