import os
import time
from collections import defaultdict

from maestro import *


# =============================================================================
# Redundancias gerais
# =============================================================================


def caminho_existente_para_ordenar(caminho):
    try:
        return (os.path.getmtime(caminho), pontuar_nome_para_manter(caminho))
    except OSError:
        return (0, pontuar_nome_para_manter(caminho))


def mover_duplicatas_do_grupo(por_hash, pasta_quarentena, inicio_etapas, executar, movidas, ausentes, erros, ultimo_progresso):
    for caminhos in por_hash.values():
        if len(caminhos) <= 1:
            continue
        caminhos = [caminho for caminho in caminhos if os.path.exists(caminho)]
        if len(caminhos) <= 1:
            continue
        caminhos.sort(key=caminho_existente_para_ordenar)
        mantido = caminhos[0]
        log(f"[MANTIDO] {mantido}")
        for copia in caminhos[1:]:
            subpasta_origem = os.path.basename(os.path.dirname(copia)) or "origem"
            try:
                destino, _ = mover_para_quarentena(copia, pasta_quarentena, inicio_etapas, [subpasta_origem], executar)
            except OSError as erro:
                erros += 1
                log(f"[ERRO] Nao movi para quarentena: {caminho_curto(copia)} ({erro})")
                continue
            if executar and destino is None:
                ausentes += 1
                continue
            movidas += 1
            mostrar, ultimo_progresso = deve_mostrar_progresso(movidas, ultimo_progresso, lote=100)
            if mostrar:
                relatorio(texto_progresso("Duplicatas ja enviadas/listadas para quarentena", movidas, None, inicio_etapas))
    return movidas, ausentes, erros, ultimo_progresso


def comando_redundancias(args):

    raiz = os.path.abspath(args.pasta)
    pasta_quarentena = os.path.join(raiz, NOME_QUARENTENA)
    inicio = time.time()
    arquivos_por_tamanho = defaultdict(list)
    total_pastas = 0
    total_arquivos = 0

    log("=== MAPEANDO ARQUIVOS ===")
    for pasta_atual, _, arquivos in iterar_arvore(raiz):
        total_pastas += 1
        for arquivo in arquivos:
            caminho = os.path.abspath(os.path.join(pasta_atual, arquivo))
            if caminho_esta_dentro(caminho, pasta_quarentena):
                continue
            try:
                tamanho = os.path.getsize(caminho)
            except OSError:
                continue
            arquivos_por_tamanho[tamanho].append(caminho)
            total_arquivos += 1
        if total_pastas % 500 == 0:
            log(f"Mapeadas {total_pastas} pastas, {total_arquivos} arquivos | {caminho_curto(pasta_atual)}")

    suspeitos = [(tamanho, caminhos) for tamanho, caminhos in arquivos_por_tamanho.items() if len(caminhos) > 1]
    total_hash = sum(len(caminhos) for _, caminhos in suspeitos)
    total_bytes_hash = sum(tamanho * len(caminhos) for tamanho, caminhos in suspeitos)
    fator = fator_disco(raiz)
    segundos_total = (
        estimar_segundos(total_pastas + total_arquivos, 1200 * fator)
        + estimar_segundos(total_bytes_hash, 55 * 1024 * 1024 * fator)
        + estimar_segundos(max(1, total_hash // 3), 18 * fator)
    )

    log("\n=== ESTIMATIVA ===")
    log(f"Pastas: {total_pastas} | Arquivos: {total_arquivos} | Suspeitos para hash: {total_hash}")
    log(f"Hash/comparacao: {estimar_hash_bytes(total_bytes_hash, raiz)}")
    log(f"Tempo total aproximado: {formatar_tempo(segundos_total)}")
    if total_hash:
        relatorio(f"RELATORIO - redundancias | {nome_alvo(raiz)}", respiro=True)
        relatorio(f"Pasta: {raiz}")
        relatorio(f"Arquivos analisados: {total_arquivos}")
        relatorio(f"Arquivos candidatos para comparacao/hash: {total_hash}")
        relatorio(f"Tamanho a ler para comparar: {formatar_bytes(total_bytes_hash)}")
        relatorio(f"Estimativa aproximada: {formatar_tempo(segundos_total)}")
        relatorio("Duplicatas serao movidas conforme cada bloco de tamanho for confirmado.")
    else:
        relatorio(f"RELATORIO - redundancias | {nome_alvo(raiz)}", respiro=True)
        relatorio(f"Pasta: {raiz}")
        relatorio(f"Arquivos analisados: {total_arquivos}")
        relatorio("Duplicatas enviadas/listadas para 1-QUARENTENA: 0")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if args.executar and not confirmar("Comparar e mover duplicatas para quarentena conforme forem encontradas?", args.sim):
        relatorio("Cancelado.")
        return
    if not args.executar:
        log("Modo simulacao: duplicatas serao listadas, mas nada sera movido. Use --executar para mover.")

    inicio_etapas = time.time()
    feitos = 0
    movidas = 0
    ausentes = 0
    erros_movimento = 0
    ultimo_hash = 0
    ultimo_movimento = 0

    for _, caminhos in suspeitos:
        por_hash = defaultdict(list)
        for caminho in caminhos:
            feitos += 1
            mostrar, ultimo_hash = deve_mostrar_progresso(feitos, ultimo_hash, lote=100, total=total_hash)
            if mostrar:
                relatorio(texto_progresso("Hash/comparacao", feitos, total_hash, inicio))
            log(f"Hash {feitos}/{total_hash}: {caminho_curto(caminho)}")
            hash_arquivo = gerar_hash(caminho)
            if hash_arquivo:
                por_hash[hash_arquivo].append(caminho)
        movidas, ausentes, erros_movimento, ultimo_movimento = mover_duplicatas_do_grupo(
            por_hash,
            pasta_quarentena,
            inicio_etapas,
            args.executar,
            movidas,
            ausentes,
            erros_movimento,
            ultimo_movimento,
        )

    acao = "enviadas" if args.executar else "que iriam"
    relatorio(f"RELATORIO - redundancias | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    relatorio(f"Arquivos analisados: {total_arquivos}")
    relatorio(f"Duplicatas {acao} para {NOME_QUARENTENA}: {movidas}")
    if ausentes:
        relatorio(f"Arquivos que sumiram antes de mover: {ausentes}")
    if erros_movimento:
        relatorio(f"Erros ao mover para quarentena: {erros_movimento}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")