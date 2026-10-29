import os
import time
from datetime import datetime

from maestro import *


# =============================================================================
# Organizar arquivos gerais por data do Windows
# =============================================================================


def ano_do_arquivo(caminho):
    try:
        return str(datetime.fromtimestamp(os.path.getmtime(caminho)).year)
    except OSError:
        return None


def parte_e_ano(parte):
    texto = str(parte).strip()
    if len(texto) != 4 or not texto.isdigit():
        return False
    ano = int(texto)
    return 1900 <= ano <= 2099


def destino_por_ano(raiz, pasta_atual, nome, ano):
    rel_pasta = os.path.relpath(pasta_atual, raiz)
    partes = [] if rel_pasta == "." else rel_pasta.split(os.sep)

    for indice, parte in enumerate(partes):
        if not parte_e_ano(parte):
            continue
        if parte == ano:
            return None
        base = os.path.join(raiz, *partes[:indice]) if indice else raiz
        resto = partes[indice + 1:]
        return os.path.join(base, ano, *resto, nome)

    return os.path.join(pasta_atual, ano, nome)


def iterar_arquivos_para_data(raiz, incluir_subpastas):
    if incluir_subpastas:
        for pasta_atual, subpastas, arquivos in os.walk(raiz, topdown=True):
            subpastas[:] = [
                subpasta
                for subpasta in subpastas
                if not ignorar_dir(subpasta)
            ]
            yield pasta_atual, arquivos
        return

    try:
        nomes = sorted(os.listdir(raiz), key=str.casefold)
    except OSError as erro:
        raise erro
    yield raiz, nomes


def comando_organizar_data(args):
    if bloquear_pasta_ampla_se_preciso(args, "pastas organizar-data"):
        return

    raiz = os.path.abspath(args.pasta)
    inicio = time.time()
    if not os.path.isdir(raiz):
        relatorio(f"[ERRO] Pasta nao encontrada: {raiz}")
        return

    incluir_subpastas = bool(getattr(args, "subpastas", False))
    candidatos = []
    erros_leitura = 0
    arquivos_analisados = 0

    try:
        iterador = iterar_arquivos_para_data(raiz, incluir_subpastas)
        for pasta_atual, nomes in iterador:
            for nome in sorted(nomes, key=str.casefold):
                caminho = os.path.join(pasta_atual, nome)
                if not os.path.isfile(caminho):
                    continue
                if nome.casefold() in ARQUIVOS_SISTEMA_IGNORADOS_PASTA_VAZIA:
                    continue
                arquivos_analisados += 1
                ano = ano_do_arquivo(caminho)
                if not ano:
                    erros_leitura += 1
                    continue
                destino_base = destino_por_ano(raiz, pasta_atual, nome, ano)
                if destino_base is None:
                    continue
                destino = gerar_caminho_unico(destino_base)
                if caminho_normalizado(caminho) == caminho_normalizado(destino):
                    continue
                candidatos.append((caminho, destino, ano))
    except OSError as erro:
        relatorio(f"[ERRO] Nao consegui listar a pasta: {raiz} ({erro})")
        return

    anos = sorted({ano for _, _, ano in candidatos})
    acao = "movidos" if args.executar else "que seriam movidos"
    escopo = "pasta e subpastas" if incluir_subpastas else "somente arquivos soltos da pasta escolhida"
    relatorio(f"RELATORIO - organizar por data | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    relatorio("Regra: usa a data de modificacao do arquivo no Windows.")
    relatorio(f"Escopo: {escopo}")
    relatorio(f"Arquivos analisados: {arquivos_analisados}")
    relatorio(f"Arquivos {acao}: {len(candidatos)}")
    relatorio(f"Pastas de ano envolvidas: {', '.join(anos) if anos else 'nenhuma'}")
    if erros_leitura:
        relatorio(f"Arquivos sem leitura de data: {erros_leitura}")

    if not candidatos:
        if not incluir_subpastas:
            relatorio("Se os arquivos estiverem dentro de subpastas, use --subpastas.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not args.executar:
        relatorio("Nada foi movido. Use --executar --sim para aplicar.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not confirmar(f"Mover {len(candidatos)} arquivo(s) para pastas de ano?", args.sim):
        relatorio("Cancelado.")
        return

    movidos = 0
    erros = 0
    ultimo_progresso = 0
    total = len(candidatos)
    for indice, (origem, destino, _) in enumerate(candidatos, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=total)
        if mostrar:
            relatorio(texto_progresso("Organizando por ano", indice, total, inicio))
        try:
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            mover_com_historico(origem, destino, executar=True)
            movidos += 1
        except OSError as erro:
            erros += 1
            log(f"[ERRO] {origem} -> {destino} ({erro})")

    relatorio(f"Arquivos movidos: {movidos}")
    relatorio(f"Erros/ignorados: {erros}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")