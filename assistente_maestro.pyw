import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


PASTA_PROGRAMA = Path(__file__).resolve().parent
MAESTRO = r".\maestro.py"


def ocultar_console_inicial():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        janela = ctypes.windll.kernel32.GetConsoleWindow()
        if janela:
            ctypes.windll.user32.ShowWindow(janela, 0)
    except Exception:
        pass


def python_para_powershell():
    if not sys.executable:
        return None
    caminho = Path(sys.executable).resolve()
    if caminho.name.casefold() == "pythonw.exe":
        python_console = caminho.with_name("python.exe")
        if python_console.exists():
            return python_console
    return caminho


PYTHON_EXE = python_para_powershell()
ocultar_console_inicial()

TAREFAS = [
    ("pastas_redundancias", "Separar arquivos duplicados", "Move copias identicas para 1-QUARENTENA.", "Procura arquivos duplicados exatos e move as copias para 1-QUARENTENA.", ["pasta", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_remover_vazias", "Eliminar pastas vazias", "Remove subpastas sem conteudo util.", "Exclui subpastas vazias em cascata, ignorando arquivos de sistema conhecidos.", ["pasta", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_dissolver", "Dissolver subpastas", "Deixa todos os arquivos soltos na pasta mae.", "Dissolve pastas e subpastas, deixando todos os arquivos soltos na pasta mae escolhida.", ["pasta", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_mesclar_similares", "Unir pastas parecidas", "Junta pastas equivalentes na mesma arvore.", "Junta pastas com nomes parecidos dentro da mesma arvore.", ["pasta", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_mesclar", "Mesclar origem no destino", "Move conteudo sem sobrescrever arquivos.", "Move o conteudo da origem para o destino com seguranca contra sobrescrita.", ["origem", "destino", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_organizar_data", "Organizar por ano", "Cria pastas de ano pela data do arquivo.", "Move arquivos para pastas de ano usando a data do Windows.", ["pasta", "subpastas_data", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_organizar_tipos", "Separar por extensao", "Cria pastas PDF, JPG, DOCX e similares.", "Move arquivos para pastas por extensao, como PDF, PNG, JPG e DOCX.", ["pasta", "subpastas_data", "executar", "sim", "detalhado", "permitir_grande"]),
    ("pastas_limpar_quarentenas", "Apagar quarentenas", "Remove pastas 1-QUARENTENA encontradas.", "Varre uma pasta pai, encontra pastas de quarentena e deleta somente com --executar.", ["pasta", "executar", "sim", "detalhado", "permitir_grande"]),
    ("desfazer", "Desfazer execucoes", "Reverte alteracoes registradas no historico.", "Desfaz uma ou mais execucoes registradas no historico.", ["pasta", "passos", "executar", "sim", "detalhado"]),
    ("limpar_historico", "Apagar historicos antigos", "Remove .maestro_historico embutidos.", "Remove pastas .maestro_historico antigas que ficaram dentro dos alvos.", ["pasta", "executar", "sim", "detalhado"]),
]
TAREFAS_POR_ID = {item[0]: item for item in TAREFAS}


class AssistenteMaestro(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Assistente Otimizar Arquivos")
        self.geometry("980x720")
        self.minsize(820, 620)

        self.tarefa_id_atual = TAREFAS[0][0]
        self.tarefa_var = tk.StringVar(value=TAREFAS[0][1])
        self.pasta_var = tk.StringVar()
        self.origem_var = tk.StringVar()
        self.destino_var = tk.StringVar()
        self.detalhado_var = tk.BooleanVar(value=False)
        self.permitir_grande_var = tk.BooleanVar(value=False)
        self.subpastas_data_var = tk.BooleanVar(value=False)
        self.passos_var = tk.StringVar(value="1")

        self.campos = {}
        self.botoes_tarefa = {}
        self._montar_tela()
        self._atualizar_visibilidade()
        self._gerar_comando()

    def _montar_tela(self):
        raiz = ttk.Frame(self, padding=16)
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(6, weight=1)

        self._configurar_estilos()

        tarefas = ttk.LabelFrame(raiz, text="Funcionalidades", padding=10)
        tarefas.grid(row=0, column=0, sticky="ew")
        tarefas.columnconfigure(0, weight=2)
        tarefas.columnconfigure(1, weight=3)
        tarefas.columnconfigure(2, weight=2)
        tarefas.columnconfigure(3, weight=3)

        for indice, (tarefa_id, nome, resumo, _descricao, _recursos) in enumerate(TAREFAS):
            grupo = indice % 2
            linha = indice // 2
            coluna_botao = grupo * 2
            coluna_resumo = coluna_botao + 1
            botao = ttk.Button(
                tarefas,
                text=nome,
                command=lambda tid=tarefa_id: self._selecionar_tarefa(tid),
            )
            botao.grid(row=linha, column=coluna_botao, sticky="ew", padx=(4, 8), pady=4)
            resumo_label = ttk.Label(tarefas, text=resumo, wraplength=230, foreground="#555555")
            resumo_label.grid(row=linha, column=coluna_resumo, sticky="w", padx=(0, 14), pady=4)
            self.botoes_tarefa[tarefa_id] = botao

        topo = ttk.Frame(raiz)
        topo.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        topo.columnconfigure(0, weight=1)

        self.nome_tarefa = ttk.Label(topo, text="", font=("Segoe UI", 11, "bold"))
        self.nome_tarefa.grid(row=0, column=0, sticky="w")
        self.descricao = ttk.Label(topo, text="", wraplength=900)
        self.descricao.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        formulario = ttk.LabelFrame(raiz, text="Dados", padding=12)
        formulario.grid(row=2, column=0, sticky="ew", pady=(14, 10))
        formulario.columnconfigure(1, weight=1)
        self.formulario = formulario

        self._linha_pasta("pasta", "Pasta", self.pasta_var, 0)
        self._linha_pasta("origem", "Origem", self.origem_var, 1)
        self._linha_pasta("destino", "Destino", self.destino_var, 2)
        self._linha_texto("passos", "Passos para desfazer", self.passos_var, 3)

        opcoes = ttk.LabelFrame(raiz, text="Opcoes", padding=12)
        opcoes.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.checks = {
            "detalhado": ttk.Checkbutton(opcoes, text="Mostrar detalhes (--detalhado)", variable=self.detalhado_var, command=self._gerar_comando),
            "permitir_grande": ttk.Checkbutton(opcoes, text="Permitir pasta grande", variable=self.permitir_grande_var, command=self._gerar_comando),
            "subpastas_data": ttk.Checkbutton(opcoes, text="Processar subpastas", variable=self.subpastas_data_var, command=self._gerar_comando),
        }
        for coluna in range(4):
            opcoes.columnconfigure(coluna, weight=1)

        botoes = ttk.Frame(raiz)
        botoes.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(botoes, text="Analisar", command=lambda: self._rodar_powershell(executar=False)).pack(side="left")
        ttk.Button(botoes, text="Efetuar", command=lambda: self._rodar_powershell(executar=True)).pack(side="left", padx=(8, 0))
        ttk.Button(botoes, text="Gerar comando", command=self._gerar_comando).pack(side="left", padx=(18, 0))
        ttk.Button(botoes, text="Copiar comando", command=self._copiar).pack(side="left", padx=(8, 0))
        ttk.Button(botoes, text="Limpar caminho", command=self._limpar_caminhos).pack(side="left", padx=(8, 0))

        ttk.Label(raiz, text="Comando que sera executado no PowerShell").grid(row=5, column=0, sticky="w")
        self.saida = tk.Text(raiz, height=9, wrap="word", undo=False)
        self.saida.grid(row=6, column=0, sticky="nsew", pady=(6, 0))
        self.saida.configure(font=("Consolas", 10))
        self._configurar_menu_saida(self.saida)

        aviso = ttk.Label(raiz, text="Analisar roda em simulacao. Efetuar aplica as mudancas de verdade.")
        aviso.grid(row=7, column=0, sticky="w", pady=(10, 0))

        for var in (self.pasta_var, self.origem_var, self.destino_var, self.passos_var):
            var.trace_add("write", lambda *_args: self._gerar_comando())

    def _configurar_estilos(self):
        estilo = ttk.Style(self)
        estilo.configure("TarefaSelecionada.TButton", font=("Segoe UI", 9, "bold"))

    def _linha_pasta(self, chave, rotulo, variavel, linha):
        label = ttk.Label(self.formulario, text=rotulo)
        entrada = ttk.Entry(self.formulario, textvariable=variavel)
        botao = ttk.Button(self.formulario, text="Escolher...", command=lambda: self._escolher_pasta(variavel))
        label.grid(row=linha, column=0, sticky="w", pady=3, padx=(0, 10))
        entrada.grid(row=linha, column=1, sticky="ew", pady=3)
        botao.grid(row=linha, column=2, sticky="e", pady=3, padx=(8, 0))
        self._configurar_menu_entrada(entrada)
        self.campos[chave] = (label, entrada, botao)

    def _linha_texto(self, chave, rotulo, variavel, linha):
        label = ttk.Label(self.formulario, text=rotulo)
        entrada = ttk.Entry(self.formulario, textvariable=variavel, width=12)
        label.grid(row=linha, column=0, sticky="w", pady=3, padx=(0, 10))
        entrada.grid(row=linha, column=1, sticky="w", pady=3)
        self._configurar_menu_entrada(entrada)
        self.campos[chave] = (label, entrada)

    def _mostrar_menu(self, menu, evento):
        try:
            evento.widget.focus_set()
            menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _selecionar_entrada(self, entrada):
        entrada.focus_set()
        entrada.selection_range(0, tk.END)
        entrada.icursor(tk.END)

    def _limpar_entrada(self, entrada):
        entrada.delete(0, tk.END)

    def _configurar_menu_entrada(self, entrada):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Recortar", command=lambda w=entrada: w.event_generate("<<Cut>>"))
        menu.add_command(label="Copiar", command=lambda w=entrada: w.event_generate("<<Copy>>"))
        menu.add_command(label="Colar", command=lambda w=entrada: w.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Selecionar tudo", command=lambda w=entrada: self._selecionar_entrada(w))
        menu.add_command(label="Limpar", command=lambda w=entrada: self._limpar_entrada(w))
        entrada.bind("<Button-3>", lambda evento, m=menu: self._mostrar_menu(m, evento))

    def _selecionar_texto(self, texto):
        texto.focus_set()
        texto.tag_add("sel", "1.0", "end-1c")
        texto.mark_set("insert", "end-1c")

    def _copiar_texto_tudo(self, texto):
        conteudo = texto.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(conteudo)

    def _configurar_menu_saida(self, texto):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copiar selecionado", command=lambda w=texto: w.event_generate("<<Copy>>"))
        menu.add_command(label="Copiar tudo", command=lambda w=texto: self._copiar_texto_tudo(w))
        menu.add_separator()
        menu.add_command(label="Selecionar tudo", command=lambda w=texto: self._selecionar_texto(w))
        texto.bind("<Button-3>", lambda evento, m=menu: self._mostrar_menu(m, evento))

    def _selecionar_tarefa(self, tarefa_id):
        self.tarefa_id_atual = tarefa_id
        self.tarefa_var.set(TAREFAS_POR_ID[tarefa_id][1])
        self._atualizar_visibilidade()
        self._pedir_caminhos_para_tarefa(forcar=True)
        self._gerar_comando()

    def _tarefa_id(self):
        return self.tarefa_id_atual

    def _atualizar_visibilidade(self):
        tarefa_id = self._tarefa_id()
        _, nome, _resumo, descricao, recursos = TAREFAS_POR_ID[tarefa_id]
        self.nome_tarefa.configure(text=nome)
        self.descricao.configure(text=descricao)

        for chave, widgets in self.campos.items():
            for widget in widgets:
                widget.grid() if chave in recursos else widget.grid_remove()

        opcoes_visiveis = [chave for chave in self.checks if chave in recursos]
        for indice, chave in enumerate(opcoes_visiveis):
            self.checks[chave].grid(row=indice // 4, column=indice % 4, sticky="w", padx=(0, 18), pady=(0, 0))

        for chave, check in self.checks.items():
            if chave not in recursos:
                check.grid_remove()

        for botao_tarefa_id, botao in self.botoes_tarefa.items():
            estilo = "TarefaSelecionada.TButton" if botao_tarefa_id == tarefa_id else "TButton"
            botao.configure(style=estilo)

    def _escolher_pasta(self, variavel, titulo="Escolha a pasta"):
        inicial = variavel.get().strip() or str(Path.home())
        escolhido = filedialog.askdirectory(initialdir=inicial, title=titulo)
        if escolhido:
            variavel.set(escolhido)
            return True
        return False

    def _pedir_caminhos_para_tarefa(self, forcar=False):
        recursos = TAREFAS_POR_ID[self._tarefa_id()][4]

        if "origem" in recursos:
            if forcar or not self.origem_var.get().strip():
                if not self._escolher_pasta(self.origem_var, "Escolha a pasta de origem"):
                    return False
            if forcar or not self.destino_var.get().strip():
                if not self._escolher_pasta(self.destino_var, "Escolha a pasta de destino"):
                    return False
            return True

        if "pasta" in recursos and (forcar or not self.pasta_var.get().strip()):
            return self._escolher_pasta(self.pasta_var)

        return True

    def _limpar_caminhos(self):
        self.pasta_var.set("")
        self.origem_var.set("")
        self.destino_var.set("")

    def _copiar(self):
        comando = self.saida.get("1.0", "end").strip()
        if not comando:
            messagebox.showwarning("Assistente Maestro", "Nao ha comando para copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(comando)
        messagebox.showinfo("Assistente Maestro", "Comando copiado.")

    def _ps(self, valor):
        valor = str(valor).strip()
        return '"' + valor.replace("`", "``").replace('"', '`"') + '"'

    def _python_partes(self):
        if PYTHON_EXE:
            return ["&", self._ps(PYTHON_EXE)]
        return ["py"]

    def _adicionar_flags_comuns(self, partes, recursos, executar):
        if "executar" in recursos and executar:
            partes.append("--executar")
        if "sim" in recursos and executar:
            partes.append("--sim")
        if "detalhado" in recursos and self.detalhado_var.get():
            partes.append("--detalhado")
        if "permitir_grande" in recursos and self.permitir_grande_var.get():
            partes.append("--permitir-pasta-grande")
        if "subpastas_data" in recursos and self.subpastas_data_var.get():
            partes.append("--subpastas")

    def _montar_partes(self, executar=False):
        tarefa_id = self._tarefa_id()
        _, _nome, _resumo, _descricao, recursos = TAREFAS_POR_ID[tarefa_id]
        pasta = self.pasta_var.get().strip()
        origem = self.origem_var.get().strip()
        destino = self.destino_var.get().strip()

        partes = self._python_partes()
        partes.append(self._ps(MAESTRO))
        if tarefa_id == "pastas_redundancias":
            partes.extend(["pastas", "redundancias", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "pastas_remover_vazias":
            partes.extend(["pastas", "remover-vazias", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "pastas_dissolver":
            partes.extend(["pastas", "dissolver", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "pastas_mesclar_similares":
            partes.extend(["pastas", "mesclar-similares", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "pastas_mesclar":
            partes.extend(["pastas", "mesclar", self._ps(origem or "CAMINHO_ORIGEM"), self._ps(destino or "CAMINHO_DESTINO")])
        elif tarefa_id == "pastas_organizar_data":
            partes.extend(["pastas", "organizar-data", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "pastas_organizar_tipos":
            partes.extend(["pastas", "organizar-tipos", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "pastas_limpar_quarentenas":
            partes.extend(["pastas", "limpar-quarentenas", self._ps(pasta or "CAMINHO_DA_PASTA")])
        elif tarefa_id == "desfazer":
            partes.extend(["desfazer", self._ps(pasta or "CAMINHO_DA_PASTA")])
            passos = self.passos_var.get().strip()
            if passos and passos != "1":
                partes.extend(["--passos", passos])
        elif tarefa_id == "limpar_historico":
            partes.extend(["limpar-historico", self._ps(pasta or "CAMINHO_DA_PASTA")])

        self._adicionar_flags_comuns(partes, recursos, executar)
        return partes

    def _montar_comando(self, executar=False, incluir_observacoes=True, para_execucao=False):
        separador = "; " if para_execucao else "\n\n"
        comando = "Set-Location -LiteralPath " + self._ps(PASTA_PROGRAMA)
        comando += separador + " ".join(self._montar_partes(executar=executar))

        if incluir_observacoes:
            observacoes = []
            if executar:
                observacoes.append("Efetuar: aplica as mudancas de verdade.")
            else:
                observacoes.append("Analisar: roda em simulacao, sem alterar arquivos.")
            if self.permitir_grande_var.get():
                observacoes.append("Cuidado: --permitir-pasta-grande libera alvos amplos.")
            if self.subpastas_data_var.get():
                observacoes.append("Com --subpastas, cada area mantem suas proprias pastas.")
            comando += "\n\n# " + "\n# ".join(observacoes)

        return comando

    def _gerar_comando(self, executar=False):
        comando = self._montar_comando(executar=executar)
        self.saida.delete("1.0", "end")
        self.saida.insert("1.0", comando)

    def _validar_para_rodar(self):
        if not self._pedir_caminhos_para_tarefa(forcar=False):
            return False

        recursos = TAREFAS_POR_ID[self._tarefa_id()][4]
        if "origem" in recursos and not self.origem_var.get().strip():
            messagebox.showwarning("Assistente Maestro", "Escolha a pasta de origem.")
            return False
        if "destino" in recursos and not self.destino_var.get().strip():
            messagebox.showwarning("Assistente Maestro", "Escolha a pasta de destino.")
            return False
        if "pasta" in recursos and not self.pasta_var.get().strip():
            messagebox.showwarning("Assistente Maestro", "Escolha a pasta.")
            return False
        return True

    def _rodar_powershell(self, executar):
        if not self._validar_para_rodar():
            return

        self._gerar_comando(executar=executar)
        comando = self._montar_comando(executar=executar, incluir_observacoes=False, para_execucao=True)
        if executar:
            argumentos = ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", comando]
            self._mostrar_texto("Efetuando em segundo plano...\n\nAguarde. O resultado aparecera aqui quando terminar.")
            threading.Thread(target=self._executar_oculto_e_mostrar, args=(argumentos,), daemon=True).start()
            return
        else:
            argumentos = ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", comando]
            opcoes = {}

        try:
            subprocess.Popen(argumentos, cwd=str(PASTA_PROGRAMA), **opcoes)
            if executar:
                messagebox.showinfo("Assistente Maestro", "Execucao iniciada em segundo plano.")
        except FileNotFoundError:
            try:
                argumentos_fallback = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", *argumentos[1:]]
                subprocess.Popen(
                    argumentos_fallback,
                    cwd=str(PASTA_PROGRAMA),
                    **opcoes,
                )
                if executar:
                    messagebox.showinfo("Assistente Maestro", "Execucao iniciada em segundo plano.")
            except OSError as erro:
                messagebox.showerror("Assistente Maestro", f"Nao consegui abrir o PowerShell:\n{erro}")
        except OSError as erro:
            messagebox.showerror("Assistente Maestro", f"Nao consegui abrir o PowerShell:\n{erro}")

    def _executar_oculto_e_mostrar(self, argumentos):
        try:
            resultado = subprocess.run(
                argumentos,
                cwd=str(PASTA_PROGRAMA),
                text=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                **self._opcoes_execucao_oculta(),
            )
        except FileNotFoundError:
            try:
                argumentos_fallback = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", *argumentos[1:]]
                resultado = subprocess.run(
                    argumentos_fallback,
                    cwd=str(PASTA_PROGRAMA),
                    text=True,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    **self._opcoes_execucao_oculta(),
                )
            except OSError as erro:
                mensagem = str(erro)
                self.after(0, lambda msg=mensagem: messagebox.showerror("Assistente Maestro", f"Nao consegui abrir o PowerShell:\n{msg}"))
                return
        except OSError as erro:
            mensagem = str(erro)
            self.after(0, lambda msg=mensagem: messagebox.showerror("Assistente Maestro", f"Nao consegui abrir o PowerShell:\n{msg}"))
            return

        saida = (resultado.stdout or "").strip()
        erro = (resultado.stderr or "").strip()
        partes = []
        if saida:
            partes.append(saida)
        if erro:
            partes.append("ERROS / AVISOS\n" + erro)
        if not partes:
            partes.append("Execucao concluida sem texto de saida.")

        status = "concluida" if resultado.returncode == 0 else f"concluida com erro (codigo {resultado.returncode})"
        texto = f"EXECUCAO {status.upper()}\n\n" + "\n\n".join(partes)
        self.after(0, lambda: self._finalizar_execucao_oculta(texto, resultado.returncode))

    def _finalizar_execucao_oculta(self, texto, codigo_saida):
        self._mostrar_texto(texto)
        if codigo_saida == 0:
            messagebox.showinfo("Assistente Maestro", "Execucao concluida. Veja o resultado na tela.")
        else:
            messagebox.showwarning("Assistente Maestro", "Execucao terminou com erro. Veja o resultado na tela.")

    def _mostrar_texto(self, texto):
        self.saida.delete("1.0", "end")
        self.saida.insert("1.0", texto)

    def _opcoes_execucao_oculta(self):
        opcoes = {
        }
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            opcoes["startupinfo"] = startupinfo
            opcoes["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return opcoes


def main():
    app = AssistenteMaestro()
    app.mainloop()


if __name__ == "__main__":
    main()
