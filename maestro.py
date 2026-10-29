import hashlib
import argparse
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import uuid
from datetime import datetime

if __name__ == "__main__":
    sys.modules["maestro"] = sys.modules[__name__]

EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif")
EXTENSOES_VIDEO = (".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm", ".3gp", ".mpeg", ".mpg")
NOME_QUARENTENA = "1-QUARENTENA"
NOMES_QUARENTENA = {NOME_QUARENTENA.lower(), "1) quarentena", "1)quarentena", "1 - quarentena", "1_quarentena", "quarentena"}
NOME_SEM_DATA = "nao_sei(verificar)"
NOME_ANO_CONFLITANTE = "ano_conflitante(verificar)"
DURACAO_ETAPA_QUARENTENA = 10 * 60
TAMANHO_BLOCO_HASH = 4 * 1024 * 1024
DETALHADO = False
RELATORIO_INICIADO = False
HISTORICO_ATUAL = None
HISTORICO_DIR = ".maestro_historico"

MESES = {
    1: "1) Janeiro",
    2: "2) Fevereiro",
    3: "3) Marco",
    4: "4) Abril",
    5: "5) Maio",
    6: "6) Junho",
    7: "7) Julho",
    8: "8) Agosto",
    9: "9) Setembro",
    10: "10) Outubro",
    11: "11) Novembro",
    12: "12) Dezembro",
}

DIRETORIOS_TECNICOS_IGNORADOS = {
    ".agents",
    ".git",
    HISTORICO_DIR,
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "env",
    "node_modules",
    "venv",
}

ARQUIVOS_SISTEMA_IGNORADOS_PASTA_VAZIA = {
    "desktop.ini",
    "thumbs.db",
}


# =============================================================================
# Funcoes utilitarias compartilhadas
# =============================================================================


def ativar_modo_detalhado(valor):
    global DETALHADO
    DETALHADO = bool(valor)


def reiniciar_relatorio():
    global RELATORIO_INICIADO
    RELATORIO_INICIADO = False


def log(mensagem=""):
    if not DETALHADO:
        return
    print(mensagem, flush=True)


def relatorio(mensagem="", respiro=False):
    global RELATORIO_INICIADO
    if respiro and RELATORIO_INICIADO:
        print("", flush=True)
    RELATORIO_INICIADO = True
    print(mensagem, flush=True)


def deve_mostrar_progresso(contador, ultimo=0, intervalo=15, lote=100, total=None):
    agora = time.time()
    if contador <= 1 or (total is not None and contador >= total):
        return True, agora
    if lote and contador % lote == 0:
        return True, agora
    if intervalo and agora - ultimo >= intervalo:
        return True, agora
    return False, ultimo


def texto_progresso(titulo, contador, total=None, inicio=None):
    partes = [titulo]
    if total:
        percentual = contador / total * 100 if total else 100
        partes.append(f"{contador}/{total} ({percentual:.1f}%)")
    else:
        partes.append(str(contador))
    if inicio is not None and contador:
        decorrido = max(0, time.time() - inicio)
        if total:
            estimado_total = decorrido / contador * total
            restante = max(0, estimado_total - decorrido)
            partes.append(f"restante aprox: {formatar_tempo(restante)}")
        else:
            partes.append(f"decorrido: {formatar_tempo(decorrido)}")
    return " | ".join(partes)

def formatar_tempo(segundos):
    segundos = max(0, int(segundos))
    minutos, segundos = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas}h {minutos}m {segundos}s"
    return f"{minutos}m {segundos}s"


def formatar_bytes(total):
    valor = float(max(0, total))
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            if unidade == "B":
                return f"{int(valor)} {unidade}"
            return f"{valor:.1f} {unidade}"
        valor /= 1024


def caminho_curto(caminho, limite=110):
    texto = str(caminho)
    if len(texto) <= limite:
        return texto
    return "..." + texto[-(limite - 3):]


def nome_alvo(caminho):
    caminho_abs = os.path.abspath(caminho)
    nome = os.path.basename(caminho_abs)
    if nome:
        return nome
    return caminho_abs


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def normalizar_nome(nome):
    return nome.strip().casefold()


def remover_acentos(texto):
    texto_normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in texto_normalizado if not unicodedata.combining(caractere))


def limpar_nome_pasta(nome):
    nome_original = nome.strip()
    if normalizar_nome(nome_original) in NOMES_QUARENTENA:
        return nome_original

    nome_limpo = nome_original
    while True:
        novo_nome = re.sub(
            r"^\s*(?:[\(\[\{]\d{1,3}[\)\]\}]|\d{1,3}[\)\]\}]|\d{1,3}\s*[-_.])\s*",
            "",
            nome_limpo,
        ).strip()
        if novo_nome == nome_limpo:
            break
        nome_limpo = novo_nome

    nome_limpo = re.sub(r"\s*[\(\[\{]\d{1,3}[\)\]\}]\s*$", "", nome_limpo).strip()
    return nome_limpo or nome_original


def caminho_normalizado(caminho):
    return os.path.normcase(os.path.abspath(caminho))


def caminho_esta_dentro(caminho, pasta):
    caminho_abs = caminho_normalizado(caminho)
    pasta_abs = caminho_normalizado(pasta)
    return caminho_abs == pasta_abs or caminho_abs.startswith(pasta_abs + os.sep)


def ignorar_dir(nome, incluir_quarentena=True):
    nome_norm = normalizar_nome(nome)
    if nome_norm in DIRETORIOS_TECNICOS_IGNORADOS:
        return True
    if remover_acentos(nome_norm) in {
        "ano_conflitante(verificar)",
        "nao sei a data (verificar)",
        "nao_sei(verificar)",
    }:
        return True
    return incluir_quarentena and nome_norm in NOMES_QUARENTENA


def confirmar(mensagem, sim):
    if sim:
        return True
    resposta = input(f"{mensagem} Digite SIM para confirmar: ").strip()
    return resposta == "SIM"


def pasta_parece_ampla_demais(caminho):
    caminho_abs = os.path.abspath(caminho)
    unidade, resto = os.path.splitdrive(caminho_abs)
    if unidade and resto in (os.sep, "\\"):
        return True

    nomes_amplos = {"estudo", "financas", "saude", "trabalho"}
    try:
        encontrados = {
            remover_acentos(nome).casefold()
            for nome in os.listdir(caminho)
            if os.path.isdir(os.path.join(caminho, nome))
        }
    except OSError:
        return False

    return len(encontrados & nomes_amplos) >= 2


def bloquear_pasta_ampla_se_preciso(args, nome_comando=None):
    if not getattr(args, "executar", False):
        return False
    if getattr(args, "permitir_pasta_grande", False):
        return False

    raiz = os.path.abspath(args.pasta)
    if not pasta_parece_ampla_demais(raiz):
        return False

    if nome_comando:
        relatorio(f"[BLOQUEADO] '{nome_comando}' parece estar apontando para uma pasta ampla demais:")
    else:
        relatorio("[BLOQUEADO] O alvo parece ser uma pasta ampla demais:")
    relatorio(raiz)
    relatorio("Escolha uma subpasta mais especifica, como um album ou uma pasta de fotos.")
    relatorio("Se tiver certeza absoluta, use --permitir-pasta-grande.")
    return True


def gerar_caminho_unico(caminho_destino):
    if not os.path.exists(caminho_destino):
        return caminho_destino

    pasta, nome_arquivo = os.path.split(caminho_destino)
    nome_base, ext = os.path.splitext(nome_arquivo)
    contador = 1
    while True:
        candidato = os.path.join(pasta, f"{nome_base}_{contador}{ext}")
        if not os.path.exists(candidato):
            return candidato
        contador += 1


def raiz_historico_id(raiz):
    raiz_abs = os.path.abspath(raiz)
    digest = hashlib.sha256(caminho_normalizado(raiz_abs).encode("utf-8", errors="ignore")).hexdigest()[:16]
    nome = re.sub(r"[^A-Za-z0-9_.-]+", "_", nome_alvo(raiz_abs)).strip("._") or "raiz"
    return f"{nome}_{digest}"


def pasta_historico_central():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), HISTORICO_DIR)


def pasta_historico_legado(raiz):
    return os.path.join(os.path.abspath(raiz), HISTORICO_DIR)


def pasta_historico(raiz):
    return os.path.join(pasta_historico_central(), "alvos", raiz_historico_id(raiz))


def pastas_historico_para_raiz(raiz):
    central = pasta_historico(raiz)
    legado = pasta_historico_legado(raiz)
    pastas = [central]
    if caminho_normalizado(central) != caminho_normalizado(legado):
        pastas.append(legado)
    return pastas


def pasta_transacoes(raiz):
    return os.path.join(pasta_historico(raiz), "transacoes")


def pasta_lixeira_historico(raiz, transacao_id):
    return os.path.join(pasta_historico(raiz), "lixeira", transacao_id)

def salvar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_json(caminho):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def iniciar_historico(raiz, comando):
    global HISTORICO_ATUAL
    raiz_abs = os.path.abspath(raiz)
    transacao_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    caminho = os.path.join(pasta_transacoes(raiz_abs), f"{transacao_id}.json")
    HISTORICO_ATUAL = {
        "id": transacao_id,
        "status": "em_andamento",
        "comando": comando,
        "raiz": raiz_abs,
        "criado_em": agora_iso(),
        "operacoes": [],
        "arquivo": caminho,
    }
    salvar_json(caminho, HISTORICO_ATUAL)


def registrar_operacao(operacao):
    if HISTORICO_ATUAL is None:
        return
    HISTORICO_ATUAL["operacoes"].append(operacao)


def finalizar_historico(status="concluido"):
    global HISTORICO_ATUAL
    if HISTORICO_ATUAL is None:
        return

    HISTORICO_ATUAL["status"] = status
    HISTORICO_ATUAL["finalizado_em"] = agora_iso()
    caminho = HISTORICO_ATUAL["arquivo"]
    if not HISTORICO_ATUAL["operacoes"]:
        try:
            os.remove(caminho)
        except OSError:
            pass
    else:
        salvar_json(caminho, HISTORICO_ATUAL)
    HISTORICO_ATUAL = None


def mover_com_historico(origem, destino, executar):
    if executar:
        shutil.move(origem, destino)
        registrar_operacao({"tipo": "move", "origem": os.path.abspath(origem), "destino": os.path.abspath(destino)})


def renomear_com_historico(origem, destino, executar):
    if executar:
        os.rename(origem, destino)
        registrar_operacao({"tipo": "move", "origem": os.path.abspath(origem), "destino": os.path.abspath(destino)})


def remover_pasta_vazia_com_historico(pasta, executar):
    if executar:
        os.rmdir(pasta)
        registrar_operacao({"tipo": "rmdir", "pasta": os.path.abspath(pasta)})


def remover_pais_vazios_ate(pasta_inicial, limite):
    pasta = os.path.abspath(pasta_inicial)
    limite = os.path.abspath(limite)
    while caminho_esta_dentro(pasta, limite):
        if not os.path.isdir(pasta):
            pasta = os.path.dirname(pasta)
            continue
        try:
            if os.listdir(pasta):
                break
            os.rmdir(pasta)
        except OSError:
            break
        if caminho_normalizado(pasta) == caminho_normalizado(limite):
            break
        pasta = os.path.dirname(pasta)


def limpar_area_auxiliar_apos_desfazer(raiz, caminho_destino_original):
    destino = os.path.abspath(caminho_destino_original)
    for nome_area in (NOME_QUARENTENA, NOME_SEM_DATA, NOME_ANO_CONFLITANTE):
        area = os.path.join(os.path.abspath(raiz), nome_area)
        if caminho_esta_dentro(destino, area):
            remover_pais_vazios_ate(os.path.dirname(destino), area)
            return


def apagar_arquivo_com_historico(caminho, executar):
    if not executar:
        return
    if HISTORICO_ATUAL is None:
        os.remove(caminho)
        return

    raiz = HISTORICO_ATUAL["raiz"]
    transacao_id = HISTORICO_ATUAL["id"]
    try:
        rel = os.path.relpath(os.path.abspath(caminho), raiz)
    except ValueError:
        rel = os.path.basename(caminho)
    destino_lixeira = gerar_caminho_unico(os.path.join(pasta_lixeira_historico(raiz, transacao_id), rel))
    os.makedirs(os.path.dirname(destino_lixeira), exist_ok=True)
    registrar_operacao({
        "tipo": "delete_file",
        "origem": os.path.abspath(caminho),
        "lixeira": os.path.abspath(destino_lixeira),
    })
    shutil.move(caminho, destino_lixeira)


def apagar_pasta_com_historico(pasta, executar):
    if not executar:
        return
    if HISTORICO_ATUAL is None:
        shutil.rmtree(pasta)
        return

    raiz = HISTORICO_ATUAL["raiz"]
    transacao_id = HISTORICO_ATUAL["id"]
    try:
        rel = os.path.relpath(os.path.abspath(pasta), raiz)
    except ValueError:
        rel = os.path.basename(pasta)
    destino_lixeira = gerar_caminho_unico(os.path.join(pasta_lixeira_historico(raiz, transacao_id), rel))
    os.makedirs(os.path.dirname(destino_lixeira), exist_ok=True)
    registrar_operacao({
        "tipo": "delete_dir",
        "origem": os.path.abspath(pasta),
        "lixeira": os.path.abspath(destino_lixeira),
    })
    shutil.move(pasta, destino_lixeira)


def transacoes_concluidas(raiz):
    transacoes = []
    vistos = set()
    for pasta in pastas_historico_para_raiz(raiz):
        pasta_transacao = os.path.join(pasta, "transacoes")
        if not os.path.isdir(pasta_transacao):
            continue
        for nome in os.listdir(pasta_transacao):
            if not nome.lower().endswith(".json"):
                continue
            caminho = os.path.join(pasta_transacao, nome)
            caminho_norm = caminho_normalizado(caminho)
            if caminho_norm in vistos:
                continue
            vistos.add(caminho_norm)
            try:
                dados = carregar_json(caminho)
            except (OSError, json.JSONDecodeError):
                continue
            status = dados.get("status")
            tem_operacoes = bool(dados.get("operacoes"))
            if status == "concluido" or (status in {"interrompido", "erro", "em_andamento"} and tem_operacoes):
                dados["arquivo"] = caminho
                transacoes.append(dados)
    return sorted(transacoes, key=lambda item: item.get("criado_em", ""), reverse=True)

def desfazer_transacao(transacao, executar):
    revertidas = 0
    conflitos = 0
    ausentes = 0

    operacoes = list(reversed(transacao.get("operacoes", [])))
    total_operacoes = len(operacoes)
    ultimo_progresso = time.time()
    for indice, operacao in enumerate(operacoes, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=total_operacoes)
        if mostrar and total_operacoes:
            relatorio(texto_progresso("Desfazendo operacoes", indice, total_operacoes, None))
        tipo = operacao.get("tipo")
        if tipo == "move":
            origem = operacao["origem"]
            destino = operacao["destino"]
            if not os.path.exists(destino):
                ausentes += 1
                continue
            if os.path.exists(origem):
                conflitos += 1
                continue
            if executar:
                os.makedirs(os.path.dirname(origem), exist_ok=True)
                shutil.move(destino, origem)
                limpar_area_auxiliar_apos_desfazer(transacao["raiz"], destino)
            revertidas += 1
        elif tipo == "rmdir":
            pasta = operacao["pasta"]
            if os.path.exists(pasta):
                conflitos += 1
                continue
            if executar:
                os.makedirs(pasta, exist_ok=True)
            revertidas += 1
        elif tipo == "delete_file":
            origem = operacao["origem"]
            lixeira = operacao["lixeira"]
            if not os.path.exists(lixeira):
                ausentes += 1
                continue
            if os.path.exists(origem):
                conflitos += 1
                continue
            if executar:
                os.makedirs(os.path.dirname(origem), exist_ok=True)
                shutil.move(lixeira, origem)
                remover_pais_vazios_ate(os.path.dirname(lixeira), pasta_lixeira_historico(transacao["raiz"], transacao["id"]))
            revertidas += 1
        elif tipo == "delete_dir":
            origem = operacao["origem"]
            lixeira = operacao["lixeira"]
            if not os.path.exists(lixeira):
                ausentes += 1
                continue
            if os.path.exists(origem):
                conflitos += 1
                continue
            if executar:
                os.makedirs(os.path.dirname(origem), exist_ok=True)
                shutil.move(lixeira, origem)
                remover_pais_vazios_ate(os.path.dirname(lixeira), pasta_lixeira_historico(transacao["raiz"], transacao["id"]))
            revertidas += 1

    return revertidas, conflitos, ausentes


def marcar_transacao_desfeita(transacao):
    transacao["status"] = "desfeito"
    transacao["desfeito_em"] = agora_iso()
    salvar_json(transacao["arquivo"], transacao)


def comando_desfazer(args):
    raiz = os.path.abspath(args.pasta)
    transacoes = transacoes_concluidas(raiz)
    passos = max(1, int(args.passos))
    escolhidas = transacoes[:passos]

    relatorio(f"RELATORIO - desfazer | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    if not escolhidas:
        relatorio("Nada para desfazer.")
        return

    if args.executar and not confirmar(f"Desfazer {len(escolhidas)} estado(s) anterior(es)?", args.sim):
        relatorio("Cancelado.")
        return

    total_operacoes = 0
    total_revertidas = 0
    total_conflitos = 0
    total_ausentes = 0
    for transacao in escolhidas:
        total_operacoes += len(transacao.get("operacoes", []))
        revertidas, conflitos, ausentes = desfazer_transacao(transacao, args.executar)
        total_revertidas += revertidas
        total_conflitos += conflitos
        total_ausentes += ausentes
        if args.executar and conflitos == 0 and ausentes == 0:
            marcar_transacao_desfeita(transacao)

    acao = "revertidas" if args.executar else "que seriam revertidas"
    relatorio(f"Estados selecionados: {len(escolhidas)}")
    relatorio(f"Operacoes registradas: {total_operacoes}")
    relatorio(f"Operacoes {acao}: {total_revertidas}")
    relatorio(f"Conflitos: {total_conflitos}")
    relatorio(f"Arquivos/pastas ausentes: {total_ausentes}")
    if not args.executar:
        relatorio("Modo simulacao: use --executar --sim para desfazer de verdade.")
def encontrar_historicos_embutidos(raiz):
    raiz_abs = os.path.abspath(raiz)
    encontrados = []
    for pasta_atual, subpastas, _ in os.walk(raiz_abs, topdown=True):
        manter = []
        for subpasta in subpastas:
            caminho = os.path.join(pasta_atual, subpasta)
            if normalizar_nome(subpasta) == normalizar_nome(HISTORICO_DIR):
                encontrados.append(caminho)
                continue
            if normalizar_nome(subpasta) in DIRETORIOS_TECNICOS_IGNORADOS:
                continue
            manter.append(subpasta)
        subpastas[:] = manter
    return sorted(encontrados, key=lambda caminho: caminho.casefold())


def medir_pasta_simples(pasta):
    arquivos = 0
    pastas = 0
    bytes_total = 0
    for _, subpastas, nomes_arquivos in os.walk(pasta):
        pastas += len(subpastas)
        arquivos += len(nomes_arquivos)
        for nome in nomes_arquivos:
            try:
                bytes_total += os.path.getsize(os.path.join(_, nome))
            except OSError:
                pass
    return arquivos, pastas + 1, bytes_total


def comando_limpar_historico(args):
    raiz = os.path.abspath(args.pasta)
    inicio = time.time()
    historicos = encontrar_historicos_embutidos(raiz)
    central = pasta_historico_central()
    historicos = [pasta for pasta in historicos if not caminho_esta_dentro(pasta, central)]

    total_arquivos = 0
    total_pastas = 0
    total_bytes = 0
    ultimo_progresso = time.time()
    for indice, historico in enumerate(historicos, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=len(historicos))
        if mostrar and historicos:
            relatorio(texto_progresso("Medindo historicos", indice, len(historicos), inicio))
        arquivos, pastas, bytes_pasta = medir_pasta_simples(historico)
        total_arquivos += arquivos
        total_pastas += pastas
        total_bytes += bytes_pasta

    relatorio(f"RELATORIO - limpar historico | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    relatorio(f"Historicos .maestro_historico encontrados: {len(historicos)}")
    relatorio(f"Pastas de historico: {total_pastas}")
    relatorio(f"Arquivos de historico/lixeira: {total_arquivos}")
    relatorio(f"Tamanho estimado: {formatar_bytes(total_bytes)}")

    if not historicos:
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return
    if not args.executar:
        relatorio("Nada foi removido. Use --executar --sim para apagar esses historicos antigos.")
        relatorio("Observacao: apagar historico remove a possibilidade de desfazer operacoes guardadas ali.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return
    if not confirmar(f"Apagar {len(historicos)} pasta(s) .maestro_historico?", args.sim):
        relatorio("Cancelado.")
        return

    removidos = 0
    erros = 0
    historicos_ordenados = sorted(historicos, key=lambda caminho: caminho.count(os.sep), reverse=True)
    ultimo_progresso = time.time()
    for indice, historico in enumerate(historicos_ordenados, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=len(historicos_ordenados))
        if mostrar:
            relatorio(texto_progresso("Removendo historicos", indice, len(historicos_ordenados), inicio))
        try:
            if os.path.isdir(historico):
                shutil.rmtree(historico)
                removidos += 1
        except OSError as erro:
            erros += 1
            log(f"[ERRO] {historico} ({erro})")

    relatorio(f"Historicos removidos: {removidos}")
    relatorio(f"Erros/ignorados: {erros}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")


def pontuar_nome_para_manter(caminho):
    nome = os.path.basename(caminho).casefold()
    penalidade_copia = int(any(texto in nome for texto in ("copia", "cÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³pia", "copy", "duplic")))
    penalidade_generico = int(bool(re.match(r"^(img|imagem|dsc|sam_|foto|image|p\d+)", nome)))
    try:
        modificado = os.path.getmtime(caminho)
    except OSError:
        modificado = 0
    return (penalidade_copia, penalidade_generico, modificado, len(nome), nome)


def obter_pasta_quarentena_etapa(pasta_quarentena, inicio_etapas):
    numero_etapa = int((time.time() - inicio_etapas) // DURACAO_ETAPA_QUARENTENA) + 1
    return os.path.join(pasta_quarentena, f"quarentena{numero_etapa}"), numero_etapa


def texto_cronometro_quarentena(inicio_etapas):
    decorrido = max(0, time.time() - inicio_etapas)
    numero_etapa = int(decorrido // DURACAO_ETAPA_QUARENTENA) + 1
    decorrido_etapa = decorrido % DURACAO_ETAPA_QUARENTENA
    restante_etapa = max(0, DURACAO_ETAPA_QUARENTENA - decorrido_etapa)
    return f"quarentena{numero_etapa} | etapa: {formatar_tempo(decorrido_etapa)} | troca em: {formatar_tempo(restante_etapa)}"


def estimar_segundos(total, velocidade_por_segundo):
    if total <= 0 or velocidade_por_segundo <= 0:
        return 0
    return total / velocidade_por_segundo


def fator_disco(caminho):
    unidade = os.path.splitdrive(os.path.abspath(caminho))[0].upper()
    unidade_programa = os.path.splitdrive(os.path.abspath(__file__))[0].upper()
    return 0.45 if unidade and unidade != unidade_programa else 1.0


def estimar_hash_bytes(total_bytes, caminho):
    return formatar_tempo(estimar_segundos(total_bytes, 55 * 1024 * 1024 * fator_disco(caminho)))


def iterar_arvore(raiz, incluir_quarentena=False, topdown=True):
    inicio = time.time()
    ultimo_progresso = time.time()
    analisadas = 0
    for pasta_atual, subpastas, arquivos in os.walk(raiz, topdown=topdown):
        analisadas += 1
        agora = time.time()
        if analisadas % 500 == 0 or agora - ultimo_progresso >= 15:
            relatorio(texto_progresso("Varredura de pastas", analisadas, None, inicio))
            ultimo_progresso = agora
        subpastas[:] = [
            subpasta
            for subpasta in subpastas
            if not ignorar_dir(subpasta, incluir_quarentena=not incluir_quarentena)
        ]
        yield pasta_atual, subpastas, arquivos


def gerar_hash(caminho):
    hasher = hashlib.sha256()
    try:
        with open(caminho, "rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(TAMANHO_BLOCO_HASH), b""):
                hasher.update(bloco)
        return hasher.hexdigest()
    except OSError:
        return None


def mover_para_quarentena(caminho, pasta_quarentena, inicio_etapas, subpastas, executar):
    if executar and not os.path.exists(caminho):
        log(f"[AUSENTE] Nao encontrei para quarentena: {caminho_curto(caminho)}")
        return None, None
    pasta_etapa, numero_etapa = obter_pasta_quarentena_etapa(pasta_quarentena, inicio_etapas)
    destino_dir = os.path.join(pasta_etapa, *subpastas)
    destino = gerar_caminho_unico(os.path.join(destino_dir, os.path.basename(caminho)))
    log(f"[{texto_cronometro_quarentena(inicio_etapas)}] {caminho_curto(caminho)} -> {caminho_curto(destino)}")
    if executar:
        try:
            os.makedirs(destino_dir, exist_ok=True)
            if not os.path.exists(caminho):
                log(f"[AUSENTE] Sumiu antes de mover: {caminho_curto(caminho)}")
                return None, None
            mover_com_historico(caminho, destino, executar=True)
        except FileNotFoundError:
            log(f"[AUSENTE] Sumiu antes de mover: {caminho_curto(caminho)}")
            return None, None
    return destino, numero_etapa


# =============================================================================
# Parser do CLI
# =============================================================================


def criar_parser():
    from dissolver import comando_dissolver
    from mesclar import comando_mesclar, comando_mesclar_duas_pastas
    from organizar_data import comando_organizar_data
    from organizar_tipos import comando_organizar_tipos
    from eliminar_pastas_vazias import comando_limpar_pastas
    from quarentenas import comando_limpar_quarentenas
    from redundancias import comando_redundancias

    parser = argparse.ArgumentParser(
        description="""Otimizador de arquivos e pastas.
Exemplos:
  py maestro.py pastas remover-vazias CAMINHO
  py maestro.py pastas mesclar ORIGEM DESTINO""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    modulos = parser.add_subparsers(dest="modulo", required=True)

    def add_flags_comuns(p, argumento_pasta=True):
        if argumento_pasta:
            p.add_argument("pasta", help="Pasta alvo")
        p.add_argument("--executar", action="store_true", help="Aplica as mudancas. Sem isso, roda em simulacao.")
        p.add_argument("--sim", action="store_true", help="Confirma automaticamente perguntas de seguranca.")
        p.add_argument("--permitir-pasta-grande", action="store_true", help="Libera execucao em raiz de disco ou pastas amplas.")
        p.add_argument("--detalhado", action="store_true", help="Mostra logs detalhados de cada arquivo/pasta.")

    def add_flags_mescla_duas_pastas(p):
        p.add_argument("origem", help="Pasta de origem")
        p.add_argument("destino", help="Pasta de destino")
        p.add_argument("--executar", action="store_true", help="Aplica as mudancas. Sem isso, roda em simulacao.")
        p.add_argument("--sim", action="store_true", help="Confirma automaticamente perguntas de seguranca.")
        p.add_argument("--permitir-pasta-grande", action="store_true", help="Libera execucao em raiz de disco ou pastas amplas.")
        p.add_argument("--detalhado", action="store_true", help="Mostra logs detalhados de cada arquivo/pasta.")

    desfazer = modulos.add_parser("desfazer", help="Desfaz uma ou mais execucoes anteriores registradas.")
    desfazer.add_argument("pasta", help="Pasta cujo historico sera usado")
    desfazer.add_argument("--passos", type=int, default=1, help="Quantidade de estados anteriores para desfazer.")
    desfazer.add_argument("--executar", action="store_true", help="Aplica o desfazer. Sem isso, roda em simulacao.")
    desfazer.add_argument("--sim", action="store_true", help="Confirma automaticamente perguntas de seguranca.")
    desfazer.add_argument("--detalhado", action="store_true", help="Mostra logs detalhados.")
    desfazer.set_defaults(func=comando_desfazer)

    limpar_historico = modulos.add_parser("limpar-historico", help="Remove pastas .maestro_historico antigas de uma pasta alvo.")
    limpar_historico.add_argument("pasta", help="Pasta onde procurar historicos antigos")
    limpar_historico.add_argument("--executar", action="store_true", help="Apaga de verdade. Sem isso, roda em simulacao.")
    limpar_historico.add_argument("--sim", action="store_true", help="Confirma automaticamente perguntas de seguranca.")
    limpar_historico.add_argument("--detalhado", action="store_true", help="Mostra logs detalhados.")
    limpar_historico.set_defaults(func=comando_limpar_historico)

    pastas = modulos.add_parser("pastas", help="Gestao de diretorios e ficheiros gerais.")
    pastas_sub = pastas.add_subparsers(dest="acao", required=True)

    p = pastas_sub.add_parser("remover-vazias", help="Remove subpastas vazias, ignorando desktop.ini e Thumbs.db.")
    add_flags_comuns(p)
    p.set_defaults(func=comando_limpar_pastas)

    p = pastas_sub.add_parser("dissolver", help="Move arquivos das subpastas para a pasta mae escolhida.")
    add_flags_comuns(p)
    p.set_defaults(func=comando_dissolver)

    p = pastas_sub.add_parser("mesclar", help="Mescla duas pastas distintas com seguranca contra sobrescrita.")
    add_flags_mescla_duas_pastas(p)
    p.set_defaults(func=comando_mesclar_duas_pastas)

    p = pastas_sub.add_parser("mesclar-similares", help="Mescla pastas parecidas dentro de uma mesma arvore.")
    add_flags_comuns(p)
    p.set_defaults(func=comando_mesclar)

    p = pastas_sub.add_parser("redundancias", help="Procura duplicatas exatas gerais e move copias para quarentena.")
    add_flags_comuns(p)
    p.set_defaults(func=comando_redundancias)

    p = pastas_sub.add_parser("limpar-quarentenas", help="Encontra e deleta pastas de quarentena abaixo de uma pasta pai.")
    add_flags_comuns(p)
    p.set_defaults(func=comando_limpar_quarentenas)

    p = pastas_sub.add_parser("organizar-data", help="Move arquivos para pastas de ano usando data de modificacao do Windows.")
    add_flags_comuns(p)
    p.add_argument("--subpastas", action="store_true", help="Tambem organiza arquivos dentro de subpastas, preservando cada area.")
    p.set_defaults(func=comando_organizar_data)

    p = pastas_sub.add_parser("organizar-tipos", help="Move arquivos para pastas por extensao, como PDF, PNG, JPG e DOCX.")
    add_flags_comuns(p)
    p.add_argument("--subpastas", action="store_true", help="Tambem organiza arquivos dentro de subpastas, preservando cada area.")
    p.set_defaults(func=comando_organizar_tipos)


    return parser


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)
    ativar_modo_detalhado(getattr(args, "detalhado", False))
    reiniciar_relatorio()
    historico_aberto = False
    if getattr(args, "executar", False) and getattr(args, "modulo", None) not in {"desfazer", "limpar-historico"}:
        raiz_historico = getattr(args, "pasta", None) or getattr(args, "destino", None)
        if raiz_historico:
            acao = getattr(args, "acao", "")
            comando = " ".join(parte for parte in (getattr(args, "modulo", ""), acao) if parte)
            iniciar_historico(raiz_historico, comando)
            historico_aberto = True
    try:
        args.func(args)
        if historico_aberto:
            finalizar_historico("concluido")
    except KeyboardInterrupt:
        if historico_aberto:
            finalizar_historico("interrompido")
            relatorio("Interrompido. O que ja tinha sido movido ficou registrado para desfazer.", respiro=True)
        raise SystemExit(130)
    except BaseException:
        if historico_aberto:
            finalizar_historico("erro")
        raise


if __name__ == "__main__":
    main()
