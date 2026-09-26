# -*- coding: utf-8 -*-
"""
sob_progress_gui.py - Interface Gráfica de Progresso com Feedback Visual Obrigatório.
Responsabilidade única: Camada de apresentação visual para acompanhamento da preparação
da SOB, exibição de estados (EM_EXECUCAO, SUCESSO, BLOQUEADO, ERRO, ROLLBACK),
indicador de atividade em tempo real e cancelamento seguro com rollback.
"""

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Optional


class ProgressoObserver:
    """
    Observer thread-safe para comunicação entre o SobOrchestrator e a UI.
    """

    def __init__(self):
        self._fila: queue.Queue = queue.Queue()
        self._cancel_event: threading.Event = threading.Event()
        self._intervencao_event: threading.Event = threading.Event()
        self._resposta_intervencao: Any = None

    def notificar(
        self,
        etapa: str,
        descricao: str,
        etapa_num: int = 1,
        total_etapas: int = 12,
        percentual: Optional[float] = None,
        estado: str = "EM_EXECUCAO",
        detalhes: Optional[Dict[str, Any]] = None,
    ):
        """Envia um evento de progresso para a fila da interface gráfica."""
        self._fila.put(
            {
                "tipo": "PROGRESSO",
                "etapa": etapa,
                "descricao": descricao,
                "etapa_num": etapa_num,
                "total_etapas": total_etapas,
                "percentual": percentual,
                "estado": estado,
                "detalhes": detalhes or {},
            }
        )

    def finalizar(self, resultado: Dict[str, Any]):
        """Notifica o encerramento do processo com o resultado final."""
        self._fila.put({"tipo": "FINALIZADO", "resultado": resultado})

    def aguardar_intervencao(self, dados: Dict[str, Any]) -> Any:
        """Bloqueia a thread trabalhadora aguardando resposta da intervenção do usuário."""
        self._intervencao_event.clear()
        self._resposta_intervencao = None
        self.notificar(
            etapa="INTERVENCAO_USUARIO",
            descricao="Múltiplas ocorrências encontradas no SharePoint. Ação necessária.",
            estado="INTERVENCAO_USUARIO",
            detalhes=dados,
        )
        self._intervencao_event.wait()
        return self._resposta_intervencao

    def perguntar_continuar_sem_gomnet(self, dados: Dict[str, Any]) -> bool:
        """Bloqueia a thread trabalhadora aguardando decisão do usuário sobre falha no GOMNET."""
        self._intervencao_event.clear()
        self._resposta_intervencao = None
        erro_txt = dados.get("erro", "Falha de conexão com o GOMNET")
        self.notificar(
            etapa="INTERVENCAO_GOMNET",
            descricao=f"Falha de acesso ao GOMNET ({erro_txt}). Decisão do usuário necessária.",
            estado="INTERVENCAO_GOMNET",
            detalhes=dados,
        )
        self._intervencao_event.wait()
        if isinstance(self._resposta_intervencao, bool):
            return self._resposta_intervencao
        if isinstance(self._resposta_intervencao, dict):
            return bool(self._resposta_intervencao.get("continuar_sem_gomnet", False))
        if isinstance(self._resposta_intervencao, str):
            return self._resposta_intervencao.strip().lower() in ("sim", "s", "true", "continuar")
        return False

    def responder_intervencao(self, resposta: Any):
        """Chamado pela interface quando o usuário toma uma ação de intervenção."""
        self._resposta_intervencao = resposta
        self._intervencao_event.set()

    def solicitar_cancelamento(self):
        """Dispara o sinal de cancelamento solicitado pelo usuário."""
        self._cancel_event.set()
        self._intervencao_event.set()
        self.notificar(
            etapa="CANCELAMENTO",
            descricao="Cancelamento solicitado. Interrompendo operação...",
            estado="CANCELAMENTO",
        )

    def cancelamento_solicitado(self) -> bool:
        """Verifica se o cancelamento foi acionado."""
        return self._cancel_event.is_set()

    def obter_evento(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Obtém o próximo evento da fila."""
        try:
            return self._fila.get(block=block, timeout=timeout)
        except queue.Empty:
            return None


class SobProgressGUI:
    """
    Janela Tkinter moderna e responsiva para feedback visual da SOB.
    Executa a lógica de orquestração em thread de background.
    """

    # Cores corporativas
    COR_NAVY = "#1B365D"
    COR_BG = "#F8FAFC"
    COR_TEXTO = "#0F172A"
    COR_SUBTEXTO = "#475569"
    COR_AZUL = "#2563EB"
    COR_VERDE = "#10B981"
    COR_VERMELHO = "#EF4444"
    COR_AMBAR = "#F59E0B"
    COR_BORDA = "#E2E8F0"

    def __init__(
        self,
        sob_id: str,
        tarefa_executora: Callable[[ProgressoObserver], Dict[str, Any]],
        auto_fechar_sucesso: bool = False,
        segundos_auto_fechar: int = 4,
        base_inicial: Optional[str] = "PE",
        root: Optional[tk.Tk] = None,
    ):
        self.sob_id = sob_id
        self.tarefa_executora = tarefa_executora
        self.auto_fechar_sucesso = auto_fechar_sucesso
        self.segundos_auto_fechar = segundos_auto_fechar
        self.base_selecionada = (base_inicial or "PE").strip().upper()

        self.observer = ProgressoObserver()
        self.observer.base_selecionada = self.base_selecionada
        self.resultado_final: Optional[Dict[str, Any]] = None
        self._thread_trabalho: Optional[threading.Thread] = None
        self._fechando = False

        self._root_proprio = root is None
        self.root = root or tk.Tk()
        self.root.title("Preparando projeto")
        self.root.geometry("540x440")
        self.root.minsize(500, 380)
        self.root.resizable(False, False)
        self.root.configure(bg=self.COR_BG)

        # Intercepta fechamento da janela
        self.root.protocol("WM_DELETE_WINDOW", self._on_fechar_janela)

        self._centralizar_janela()
        self._configurar_estilos()
        self._criar_widgets()

    def _centralizar_janela(self):
        """Centraliza a janela na tela."""
        self.root.update_idletasks()
        w = 560
        h = 490
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after_idle(self.root.attributes, "-topmost", False)
        except Exception:
            pass

    def _configurar_estilos(self):
        """Configura os estilos TTK."""
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=self.COR_BORDA,
            background=self.COR_AZUL,
            thickness=14,
        )
        self.style.configure(
            "Sucesso.Horizontal.TProgressbar",
            troughcolor=self.COR_BORDA,
            background=self.COR_VERDE,
            thickness=14,
        )
        self.style.configure(
            "Erro.Horizontal.TProgressbar",
            troughcolor=self.COR_BORDA,
            background=self.COR_VERMELHO,
            thickness=14,
        )
        self.style.configure(
            "Alerta.Horizontal.TProgressbar",
            troughcolor=self.COR_BORDA,
            background=self.COR_AMBAR,
            thickness=14,
        )

    def _criar_widgets(self):
        """Monta os componentes visuais."""
        # Topo / Cabeçalho
        frame_cabecalho = tk.Frame(self.root, bg=self.COR_NAVY, padx=20, pady=14)
        frame_cabecalho.pack(fill="x")

        lbl_titulo = tk.Label(
            frame_cabecalho,
            text="Preparando projeto",
            font=("Segoe UI", 13, "bold"),
            bg=self.COR_NAVY,
            fg="#FFFFFF",
        )
        lbl_titulo.pack(anchor="w")

        lbl_sob = tk.Label(
            frame_cabecalho,
            text=f"SOB: {self.sob_id}  |  Base: {self.base_selecionada}",
            font=("Segoe UI", 11),
            bg=self.COR_NAVY,
            fg="#93C5FD",
        )
        lbl_sob.pack(anchor="w", pady=(2, 0))

        # Corpo
        frame_corpo = tk.Frame(self.root, bg=self.COR_BG, padx=24, pady=18)
        frame_corpo.pack(fill="both", expand=True)

        # Indicador de etapa
        self.lbl_etapa_badge = tk.Label(
            frame_corpo,
            text="Iniciando...",
            font=("Segoe UI", 9, "bold"),
            bg="#E0E7FF",
            fg=self.COR_AZUL,
            padx=8,
            pady=3,
        )
        self.lbl_etapa_badge.pack(anchor="w", pady=(0, 8))

        # Descrição da atividade atual
        self.lbl_descricao = tk.Label(
            frame_corpo,
            text="● Iniciando preparação da SOB...",
            font=("Segoe UI", 11, "bold"),
            bg=self.COR_BG,
            fg=self.COR_TEXTO,
            wraplength=470,
            justify="left",
        )
        self.lbl_descricao.pack(anchor="w", fill="x")

        # Detalhes adicionais
        self.lbl_detalhes = tk.Label(
            frame_corpo,
            text="Aguardando inicialização das validações.",
            font=("Segoe UI", 9),
            bg=self.COR_BG,
            fg=self.COR_SUBTEXTO,
            wraplength=470,
            justify="left",
        )
        self.lbl_detalhes.pack(anchor="w", fill="x", pady=(4, 16))

        # Barra de progresso
        self.progresso_bar = ttk.Progressbar(
            frame_corpo,
            orient="horizontal",
            mode="indeterminate",
            style="Horizontal.TProgressbar",
        )
        self.progresso_bar.pack(fill="x", pady=(0, 6))
        self.progresso_bar.start(12)

        # Mensagem de estado final
        self.lbl_mensagem_final = tk.Label(
            frame_corpo,
            text="",
            font=("Segoe UI", 9),
            bg=self.COR_BG,
            fg=self.COR_TEXTO,
            wraplength=470,
            justify="left",
        )
        self.lbl_mensagem_final.pack(anchor="w", fill="x")

        # Painel de Intervenção Manual (visível em INTERVENCAO_USUARIO)
        self._url_busca = ""
        self._pasta_selecionada = Path.home() / "Downloads"

        self.frame_intervencao = tk.Frame(frame_corpo, bg="#F1F5F9", relief="solid", bd=1, padx=12, pady=10)

        self.lbl_aviso_intervencao = tk.Label(
            self.frame_intervencao,
            text="Localização manual necessária no SharePoint.\n"
                 "Abra o link, copie o link da pasta correta e cole abaixo:",
            font=("Segoe UI", 9, "bold"),
            bg="#F1F5F9",
            fg=self.COR_TEXTO,
            justify="left",
        )
        self.lbl_aviso_intervencao.pack(anchor="w", pady=(0, 4))

        frame_linha_sp = tk.Frame(self.frame_intervencao, bg="#F1F5F9")
        frame_linha_sp.pack(fill="x", pady=(0, 4))

        self.btn_abrir_sp = tk.Button(
            frame_linha_sp,
            text="🌐 Abrir SharePoint",
            font=("Segoe UI", 9, "bold"),
            bg="#DBEAFE",
            fg="#1E40AF",
            activebackground="#BFDBFE",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._abrir_sharepoint,
        )
        self.btn_abrir_sp.pack(side="left")

        lbl_dica_sp = tk.Label(
            frame_linha_sp,
            text="(Abre a pasta de levantamentos)",
            font=("Segoe UI", 8),
            bg="#F1F5F9",
            fg=self.COR_SUBTEXTO,
        )
        lbl_dica_sp.pack(side="left", padx=(6, 0))

        # Campo para colar link da pasta do SharePoint
        frame_link_sp = tk.Frame(self.frame_intervencao, bg="#F1F5F9")
        frame_link_sp.pack(fill="x", pady=(2, 4))

        lbl_link_tit = tk.Label(
            frame_link_sp,
            text="🔗 Cole o link da pasta da SOB no SharePoint:",
            font=("Segoe UI", 8, "bold"),
            bg="#F1F5F9",
            fg=self.COR_TEXTO,
            anchor="w",
        )
        lbl_link_tit.pack(fill="x", pady=(0, 2))

        frame_input_link = tk.Frame(frame_link_sp, bg="#F1F5F9")
        frame_input_link.pack(fill="x")

        self.ent_link_sp = ttk.Entry(frame_input_link, font=("Segoe UI", 9))
        self.ent_link_sp.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_colar_link = tk.Button(
            frame_input_link,
            text="📋 Colar",
            font=("Segoe UI", 8),
            bg="#E2E8F0",
            fg=self.COR_TEXTO,
            activebackground="#CBD5E1",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._colar_link_clipboard,
        )
        self.btn_colar_link.pack(side="right")

        # Opção alternativa: selecionar pasta local se o usuário já baixou manualmente
        frame_pasta_local = tk.Frame(self.frame_intervencao, bg="#F1F5F9")
        frame_pasta_local.pack(fill="x", pady=(2, 6))

        self.btn_sel_pasta = tk.Button(
            frame_pasta_local,
            text="📁 Ou Selecionar Pasta Local...",
            font=("Segoe UI", 8),
            bg="#E2E8F0",
            fg=self.COR_TEXTO,
            activebackground="#CBD5E1",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._selecionar_pasta_dialog,
        )
        self.btn_sel_pasta.pack(side="left")

        self.lbl_caminho_pasta = tk.Label(
            frame_pasta_local,
            text=f"Pasta: {self._pasta_selecionada}",
            font=("Segoe UI", 8),
            bg="#F1F5F9",
            fg=self.COR_SUBTEXTO,
            anchor="w",
        )
        self.lbl_caminho_pasta.pack(side="left", padx=(6, 0), fill="x", expand=True)

        # Botões de decisão da intervenção
        frame_acoes_intervencao = tk.Frame(self.frame_intervencao, bg="#F1F5F9")
        frame_acoes_intervencao.pack(fill="x")

        self.btn_intervencao_continuar = tk.Button(
            frame_acoes_intervencao,
            text="Continuar",
            font=("Segoe UI", 9, "bold"),
            bg=self.COR_AZUL,
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
            command=self._confirmar_intervencao,
        )
        self.btn_intervencao_continuar.pack(side="left")

        self.btn_intervencao_sem_croqui = tk.Button(
            frame_acoes_intervencao,
            text="Continuar sem Croqui",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg=self.COR_TEXTO,
            activebackground="#CBD5E1",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._confirmar_sem_croqui,
        )
        self.btn_intervencao_sem_croqui.pack(side="left", padx=(8, 0))

        self.btn_intervencao_cancelar = tk.Button(
            frame_acoes_intervencao,
            text="Cancelar",
            font=("Segoe UI", 9),
            bg="#FEE2E2",
            fg="#991B1B",
            activebackground="#FCA5A5",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._cancelar_intervencao,
        )
        self.btn_intervencao_cancelar.pack(side="right")

        # Rodapé / Ações
        frame_rodape = tk.Frame(self.root, bg=self.COR_BG, padx=24, pady=12)
        frame_rodape.pack(fill="x", side="bottom")

        self.btn_cancelar = tk.Button(
            frame_rodape,
            text="Cancelar",
            font=("Segoe UI", 10),
            bg="#FEE2E2",
            fg="#991B1B",
            activebackground="#FCA5A5",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._solicitar_cancelamento,
        )
        self.btn_cancelar.pack(side="right", padx=(8, 0))

        self.btn_fechar = tk.Button(
            frame_rodape,
            text="Concluir",
            font=("Segoe UI", 10, "bold"),
            bg=self.COR_AZUL,
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            relief="flat",
            padx=16,
            pady=4,
            cursor="hand2",
            command=self._fechar_janela,
        )
        self.btn_fechar.pack_forget()

    def _abrir_sharepoint(self):
        """Abre o SharePoint no navegador contextualizado com a SOB."""
        from sob_fallback_manual import abrir_busca_sharepoint_navegador
        abrir_busca_sharepoint_navegador(self.sob_id, self._url_busca)

    def _selecionar_pasta_dialog(self):
        """Abre diálogo para seleção da pasta onde o usuário salvou os downloads."""
        from tkinter import filedialog
        pasta = filedialog.askdirectory(
            title="Selecione a pasta com os arquivos baixados da SOB",
            initialdir=str(self._pasta_selecionada),
        )
        if pasta:
            self._pasta_selecionada = Path(pasta).resolve()
            self.lbl_caminho_pasta.configure(text=f"Pasta: {self._pasta_selecionada}")

    def _colar_link_clipboard(self):
        """Cola o texto da área de transferência no campo do link do SharePoint."""
        try:
            texto = self.root.clipboard_get()
            if texto and hasattr(self, "ent_link_sp"):
                self.ent_link_sp.delete(0, "end")
                self.ent_link_sp.insert(0, texto.strip())
        except Exception:
            pass

    def _confirmar_intervencao(self):
        """Dispara a validação: prioriza link do SharePoint se informado, senão pasta local."""
        link_digitado = self.ent_link_sp.get().strip() if hasattr(self, "ent_link_sp") else ""
        if link_digitado and (link_digitado.startswith("http") or "sharepoint.com" in link_digitado):
            self.lbl_detalhes.configure(text="Link do SharePoint recebido. Baixando conteúdo...")
            self.observer.responder_intervencao({"url_sharepoint": link_digitado})
        else:
            self.lbl_detalhes.configure(text="Validando arquivos manuais...")
            self.observer.responder_intervencao({"caminho": str(self._pasta_selecionada)})

    def _confirmar_sem_croqui(self):
        """Confirma a continuidade da operação sem arquivos de croqui (CROQUI = SEM_ARQUIVOS)."""
        self.lbl_detalhes.configure(text="Continuando sem arquivos de croqui...")
        self.observer.responder_intervencao({"sem_croqui": True})

    def _cancelar_intervencao(self):
        """Cancela a operação durante o diálogo de intervenção."""
        self.lbl_detalhes.configure(text="Cancelando operação...")
        self.observer.responder_intervencao({"cancelar": True})

    def _solicitar_cancelamento(self):
        """Manipula o clique em Cancelar."""
        self.btn_cancelar.configure(state="disabled", text="Cancelando...")
        self.lbl_etapa_badge.configure(text="Cancelamento solicitado", bg="#FEF3C7", fg=self.COR_AMBAR)
        self.lbl_descricao.configure(text="● Interrompendo operação...")
        self.lbl_detalhes.configure(text="Finalizando operação atual... O cancelamento será aplicado em seguida.")
        self.observer.solicitar_cancelamento()

    def _on_fechar_janela(self):
        """Ao tentar fechar a janela durante a execução."""
        if self._thread_trabalho and self._thread_trabalho.is_alive():
            if not self.observer.cancelamento_solicitado():
                self._solicitar_cancelamento()
        else:
            self._fechar_janela()

    def _fechar_janela(self):
        """Fecha a interface."""
        self._fechando = True
        try:
            if self._root_proprio:
                self.root.destroy()
            else:
                self.root.quit()
        except Exception:
            pass

    def iniciar(self) -> Dict[str, Any]:
        """
        Inicia a janela e a thread de trabalho.
        Bloqueia até o fechamento da janela e retorna o resultado final.
        """
        def _executar_em_background():
            try:
                res = self.tarefa_executora(self.observer)
                self.observer.finalizar(res)
            except Exception as e:
                self.observer.finalizar(
                    {
                        "sucesso": False,
                        "status": "BLOQUEADO",
                        "estado": "ERRO",
                        "mensagem": f"[FALHA] Erro inesperado: {str(e)}",
                    }
                )

        self._thread_trabalho = threading.Thread(target=_executar_em_background, daemon=True)
        self._thread_trabalho.start()

        # Inicia o polling de eventos
        self.root.after(50, self._processar_eventos)
        self.root.mainloop()

        return self.resultado_final or {
            "sucesso": False,
            "status": "BLOQUEADO",
            "mensagem": "Janela encerrada antes da conclusão.",
        }

    def _processar_eventos(self):
        """Consome eventos da fila e atualiza os componentes gráficos."""
        if self._fechando:
            return

        while True:
            evento = self.observer.obter_evento()
            if not evento:
                break

            tipo = evento.get("tipo")
            if tipo == "PROGRESSO":
                self._atualizar_progresso(evento)
            elif tipo == "FINALIZADO":
                self._tratar_finalizacao(evento.get("resultado", {}))

        if not self._fechando:
            self.root.after(60, self._processar_eventos)

    def _atualizar_progresso(self, ev: Dict[str, Any]):
        """Atualiza a UI com um evento de progresso."""
        etapa_num = ev.get("etapa_num", 1)
        total_etapas = ev.get("total_etapas", 12)
        descricao = ev.get("descricao", "")
        estado = ev.get("estado", "EM_EXECUCAO")
        percentual = ev.get("percentual")

        # Badge de etapa e configuração de intervenção
        detalhes = ev.get("detalhes", {})
        if estado == "INTERVENCAO_USUARIO":
            self.lbl_etapa_badge.configure(text="Ação Necessária", bg="#FEF3C7", fg=self.COR_AMBAR)
            if detalhes.get("url_busca"):
                self._url_busca = detalhes["url_busca"]
            if detalhes.get("pasta_sugerida"):
                self._pasta_selecionada = Path(detalhes["pasta_sugerida"])
                self.lbl_caminho_pasta.configure(text=f"Pasta: {self._pasta_selecionada}")

            motivo = detalhes.get("motivo", "")
            if "NÃO_ENCONTRADA" in motivo:
                self.lbl_aviso_intervencao.configure(
                    text="SOB não localizada automaticamente no SharePoint.\n"
                         "Abra o SharePoint, copie o link da pasta correta e cole abaixo:"
                )
            else:
                self.lbl_aviso_intervencao.configure(
                    text="Múltiplas ocorrências encontradas no SharePoint.\n"
                         "Abra o SharePoint, copie o link da pasta correta e cole abaixo:"
                )

            self.frame_intervencao.pack(fill="x", pady=(8, 0))
            self.btn_cancelar.pack_forget()
            self.progresso_bar.stop()
            self.progresso_bar.configure(mode="determinate", value=100, style="Alerta.Horizontal.TProgressbar")
            self.lbl_detalhes.configure(text="Aguardando intervenção manual do usuário no SharePoint.")

        elif estado == "FALHA_VALIDACAO_MANUAL":
            self.lbl_etapa_badge.configure(text="Não foi possível validar o download", bg="#FEE2E2", fg=self.COR_VERMELHO)
            self.frame_intervencao.pack(fill="x", pady=(8, 0))
            self.btn_cancelar.pack_forget()
            self.lbl_detalhes.configure(
                text=f"Nenhum arquivo válido encontrado para SOB {self.sob_id}. "
                     f"Selecione a pasta correta ou tente novamente."
            )
        elif estado == "INTERVENCAO_GOMNET":
            self.lbl_etapa_badge.configure(text="Aviso: GOMNET", bg="#FEF3C7", fg=self.COR_AMBAR)
            erro_msg = detalhes.get("erro", "Falha de comunicação com o GOMNET.")
            self.lbl_descricao.configure(text="● Falha ao acessar o GOMNET")
            self.lbl_detalhes.configure(text=f"Aviso: {erro_msg}")
            self.progresso_bar.stop()

            # Pergunta ao usuário se deseja continuar sem o fluxo do GOMNET ou fazer rollback
            try:
                resposta = messagebox.askyesno(
                    title="GOMNET - Continuar ou Rollback?",
                    message=(
                        f"Ocorreu um erro ao acessar o GOMNET:\n\n{erro_msg}\n\n"
                        "Deseja continuar a preparação da SOB sem o fluxo do GOMNET?\n\n"
                        "• Sim: Continuar a preparação sem os dados/anexos do GOMNET\n"
                        "• Não: Cancelar a operação e fazer Rollback"
                    ),
                    parent=self.root,
                )
            except Exception:
                resposta = False
            self.observer.responder_intervencao(resposta)
        else:
            # Em fluxo normal, esconde painel de intervenção
            self.frame_intervencao.pack_forget()
            if not self.btn_cancelar.winfo_ismapped() and not self.btn_fechar.winfo_ismapped():
                self.btn_cancelar.pack(side="right", padx=(8, 0))

            if estado == "CANCELAMENTO":
                self.lbl_etapa_badge.configure(text="Cancelamento solicitado", bg="#FEF3C7", fg=self.COR_AMBAR)
            elif estado.startswith("ROLLBACK"):
                self.lbl_etapa_badge.configure(text=estado.replace("_", " ").title(), bg="#FEE2E2", fg=self.COR_VERMELHO)
            else:
                self.lbl_etapa_badge.configure(
                    text=f"Etapa {etapa_num} de {total_etapas}",
                    bg="#E0E7FF",
                    fg=self.COR_AZUL,
                )

        self.lbl_descricao.configure(text=f"● {descricao}")

        # Configuração da barra de progresso (Determinada vs Indeterminada)
        if estado not in ("INTERVENCAO_USUARIO", "FALHA_VALIDACAO_MANUAL"):
            if percentual is not None:
                self.progresso_bar.stop()
                self.progresso_bar.configure(mode="determinate", maximum=100, value=percentual)
                self.lbl_detalhes.configure(text=f"Progresso: {int(percentual)}% concluído.")
            else:
                if self.progresso_bar["mode"] != "indeterminate":
                    self.progresso_bar.configure(mode="indeterminate", style="Horizontal.TProgressbar")
                    self.progresso_bar.start(12)
                self.lbl_detalhes.configure(text="Processando requisição...")

    def _tratar_finalizacao(self, res: Dict[str, Any]):
        """Trata a conclusão da operação."""
        self.resultado_final = res
        self.progresso_bar.stop()
        self.btn_cancelar.pack_forget()
        self.btn_fechar.pack(side="right")

        sucesso = res.get("sucesso", False)
        status = res.get("status", "BLOQUEADO")
        msg = res.get("mensagem", "")
        rollback = res.get("rollback", "ROLLBACK_NÃO_NECESSÁRIO")

        if sucesso:
            self.progresso_bar.configure(mode="determinate", value=100, style="Sucesso.Horizontal.TProgressbar")
            self.lbl_etapa_badge.configure(text="Concluído", bg="#D1FAE5", fg=self.COR_VERDE)
            self.lbl_descricao.configure(text="✔ Projeto preparado com sucesso!")
            self.lbl_detalhes.configure(text="Arquivo BASE_SOB_DESENHO.dwg gerado e validado.")
            self.lbl_mensagem_final.configure(
                text=f"Destino: {res.get('SOB_ROOT', '')}",
                fg=self.COR_SUBTEXTO,
            )
            self.btn_fechar.configure(text="Concluir", bg=self.COR_VERDE)

            if self.auto_fechar_sucesso:
                self.root.after(self.segundos_auto_fechar * 1000, self._fechar_janela)

        elif status == "BLOQUEADO" and self.observer.cancelamento_solicitado():
            self.progresso_bar.configure(mode="determinate", value=100, style="Alerta.Horizontal.TProgressbar")
            self.lbl_etapa_badge.configure(text="Cancelado", bg="#FEF3C7", fg=self.COR_AMBAR)
            self.lbl_descricao.configure(text="⚠ Operação cancelada pelo usuário.")
            self.lbl_detalhes.configure(text=f"Status de Rollback: {rollback}.")
            self.lbl_mensagem_final.configure(
                text="Nenhum recurso corrompido foi mantido.",
                fg=self.COR_SUBTEXTO,
            )
            self.btn_fechar.configure(text="Fechar", bg=self.COR_AMBAR)

        else:
            self.progresso_bar.configure(mode="determinate", value=100, style="Erro.Horizontal.TProgressbar")
            self.lbl_etapa_badge.configure(text="Operação Bloqueada", bg="#FEE2E2", fg=self.COR_VERMELHO)
            etapa_falha = res.get("etapa", "Falha Operacional")
            self.lbl_descricao.configure(text=f"✖ Bloqueio na etapa: {etapa_falha}")
            self.lbl_detalhes.configure(text=msg or "Condições obrigatórias não foram atendidas.")
            if rollback != "ROLLBACK_NÃO_NECESSÁRIO":
                self.lbl_mensagem_final.configure(
                    text=f"Mecanismo de reversão aplicado: {rollback}",
                    fg=self.COR_VERMELHO,
                )
            self.btn_fechar.configure(text="Fechar", bg=self.COR_VERMELHO)
