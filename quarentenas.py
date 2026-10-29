import os
import time

from maestro import *


# =============================================================================
# Remover quarentenas em massa
# =============================================================================


def nome_e_quarentena(nome):
    nome_norm = normalizar_nome(nome)
    if nome_norm in NOMES_QUARENTENA:
        return True
    return normalizar_nome(limpar_nome_pasta(nome)) in NOMES_QUARENTENA


def encontrar_quarentenas(raiz):
    quarentenas = []
    inicio = time.time()
    ultimo_progresso = 0
    analisadas = 0
    for pasta_atual, subpastas, _ in os.walk(raiz, topdown=True):
        analisadas += 1
        mostrar, ultimo_progresso = deve_mostrar_progresso(analisadas, ultimo_progresso, lote=500)
        if mostrar:
            relatorio(texto_progresso("Procurando quarentenas", analisadas, None, inicio))
        manter = []
        for subpasta in subpastas:
            nome_norm = normalizar_nome(subpasta)
            caminho = os.path.join(pasta_atual, subpasta)
            if nome_norm in DIRETORIOS_TECNICOS_IGNORADOS:
                continue
            if nome_e_quarentena(subpasta):
                quarentenas.append(caminho)
                continue
            manter.append(subpasta)
        subpastas[:] = manter
    return sorted(quarentenas, key=lambda caminho: caminho.casefold())


def medir_pasta(pasta):
    arquivos = 0
    subpastas = 0
    bytes_total = 0
    erros = 0

    for _, nomes_pastas, nomes_arquivos in os.walk(pasta):
        subpastas += len(nomes_pastas)
        arquivos += len(nomes_arquivos)
        for nome_arquivo in nomes_arquivos:
            caminho = os.path.join(_, nome_arquivo)
            try:
                bytes_total += os.path.getsize(caminho)
            except OSError:
                erros += 1

    return arquivos, subpastas, bytes_total, erros


def comando_limpar_quarentenas(args):
    if bloquear_pasta_ampla_se_preciso(args, "pastas limpar-quarentenas"):
        return

    inicio = time.time()
    raiz = os.path.abspath(args.pasta)
    quarentenas = encontrar_quarentenas(raiz)

    total_arquivos = 0
    total_subpastas = 0
    total_bytes = 0
    total_erros_leitura = 0
    total_quarentenas = len(quarentenas)
    ultimo_progresso = 0
    for indice, quarentena in enumerate(quarentenas, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=25, total=total_quarentenas)
        if mostrar:
            relatorio(texto_progresso("Medindo quarentenas", indice, total_quarentenas, inicio))
        arquivos, subpastas, bytes_pasta, erros = medir_pasta(quarentena)
        total_arquivos += arquivos
        total_subpastas += subpastas + 1
        total_bytes += bytes_pasta
        total_erros_leitura += erros
        log(f"[QUARENTENA] {caminho_curto(quarentena)} | {arquivos} arquivo(s)")

    relatorio(f"RELATORIO - limpar quarentenas | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta pai: {raiz}")
    relatorio(f"Quarentenas encontradas: {len(quarentenas)}")
    acao_pastas = "removidas" if args.executar else "que seriam removidas"
    acao_arquivos = "removidos" if args.executar else "que seriam removidos"
    relatorio(f"Pastas {acao_pastas}: {total_subpastas}")
    relatorio(f"Arquivos {acao_arquivos}: {total_arquivos}")
    relatorio(f"Tamanho estimado: {formatar_bytes(total_bytes)}")

    if total_erros_leitura:
        relatorio(f"Arquivos sem leitura de tamanho: {total_erros_leitura}")

    if not quarentenas:
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not args.executar:
        relatorio("Nada foi deletado. Use --executar --sim para remover de verdade.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not confirmar(f"Deletar {len(quarentenas)} pasta(s) de quarentena?", args.sim):
        relatorio("Cancelado.")
        return

    removidas = 0
    erros_remocao = 0
    ultimo_progresso = 0
    for indice, quarentena in enumerate(sorted(quarentenas, key=lambda caminho: caminho.count(os.sep), reverse=True), start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=25, total=total_quarentenas)
        if mostrar:
            relatorio(texto_progresso("Removendo quarentenas", indice, total_quarentenas, inicio))
        try:
            if os.path.isdir(quarentena):
                apagar_pasta_com_historico(quarentena, executar=True)
                removidas += 1
        except OSError as erro:
            erros_remocao += 1
            log(f"[IGNORADA] Nao foi possivel remover: {quarentena} ({erro})")

    relatorio(f"Quarentenas removidas: {removidas}")
    relatorio(f"Erros/ignoradas: {erros_remocao}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")

