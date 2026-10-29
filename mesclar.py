import argparse
import os
import time
from collections import defaultdict

from maestro import *


# =============================================================================
# Mesclar pastas
# =============================================================================
def limpar_nome_pasta_para_mescla(nome):
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


def chave_nome_pasta_para_mescla(nome):
    nome_limpo = limpar_nome_pasta_para_mescla(nome)
    nome_sem_acentos = remover_acentos(nome_limpo).casefold()
    nome_sem_pontuacao = re.sub(r"[^\w\s]", " ", nome_sem_acentos)
    return re.sub(r"\s+", " ", nome_sem_pontuacao).strip()


def estimar_varredura(pastas, arquivos, caminho):
    return formatar_tempo(estimar_segundos(pastas + arquivos, 1200 * fator_disco(caminho)))


def encontrar_pasta_equivalente(pasta_destino, nome_origem):
    chave_origem = chave_nome_pasta_para_mescla(nome_origem)
    if not os.path.isdir(pasta_destino):
        return None

    for nome in os.listdir(pasta_destino):
        caminho = os.path.join(pasta_destino, nome)
        if os.path.isdir(caminho) and chave_nome_pasta_para_mescla(nome) == chave_origem:
            return caminho
    return None


def mover_item_mesclando(origem, pasta_destino, executar):
    nome = os.path.basename(origem)
    if os.path.isdir(origem):
        destino = encontrar_pasta_equivalente(pasta_destino, nome)
        if destino is None:
            destino = os.path.join(pasta_destino, limpar_nome_pasta_para_mescla(nome))

        if os.path.exists(destino) and os.path.isdir(destino):
            for item in os.listdir(origem):
                mover_item_mesclando(os.path.join(origem, item), destino, executar)
            if executar:
                try:
                    remover_pasta_vazia_com_historico(origem, executar=True)
                except OSError:
                    pass
            return

        destino = gerar_caminho_unico(destino)
        log(f"[MESCLAR] {origem} -> {destino}")
        if executar:
            mover_com_historico(origem, destino, executar=True)
        return

    destino = gerar_caminho_unico(os.path.join(pasta_destino, nome))
    log(f"[MOVER] {origem} -> {destino}")
    if executar:
        mover_com_historico(origem, destino, executar=True)


def escolher_destino_mescla(caminhos, executar):
    destino = sorted(
        caminhos,
        key=lambda caminho: (
            os.path.basename(caminho) != limpar_nome_pasta_para_mescla(os.path.basename(caminho)),
            len(os.path.basename(caminho)),
            os.path.basename(caminho).casefold(),
        ),
    )[0]
    destino_original = destino
    nome_limpo = limpar_nome_pasta_para_mescla(os.path.basename(destino))
    destino_limpo = os.path.join(os.path.dirname(destino), nome_limpo)

    if caminho_normalizado(destino) == caminho_normalizado(destino_limpo):
        return destino, destino_original

    if os.path.isdir(destino_limpo):
        return destino_limpo, destino_original

    if not os.path.exists(destino_limpo):
        log(f"[RENOMEAR DESTINO] {destino} -> {destino_limpo}")
        if executar:
            renomear_com_historico(destino, destino_limpo, executar=True)
        return destino_limpo, destino_original

    return destino, destino_original


def comando_mesclar(args):
    raiz = os.path.abspath(args.pasta)
    pais = []
    inicio = time.time()
    for pasta_atual, _, _ in iterar_arvore(raiz):
        pais.append(pasta_atual)
        if len(pais) % 500 == 0:
            log(f"Mapeando pastas: {len(pais)} | {caminho_curto(pasta_atual)}")

    log("\n=== ESTIMATIVA ===")
    log(f"Pastas para analisar: {len(pais)}")
    log(f"Tempo aproximado: {formatar_tempo(estimar_segundos(len(pais), 650 * fator_disco(raiz)))}")
    if not args.executar:
        log("=== MODO SIMULACAO ===")
        log("Nada sera movido ou renomeado. Use --executar para aplicar de verdade.")

    mescladas = 0
    total_pais = len(pais)
    ultimo_progresso = 0
    for indice, pasta_pai in enumerate(sorted(pais, key=lambda caminho: caminho.count(os.sep), reverse=True), 1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=200, total=total_pais)
        if mostrar:
            relatorio(texto_progresso("Analisando pastas similares", indice, total_pais, inicio))

        try:
            nomes = os.listdir(pasta_pai)
        except OSError:
            continue

        grupos = defaultdict(list)
        for nome in nomes:
            caminho = os.path.join(pasta_pai, nome)
            if os.path.isdir(caminho) and not ignorar_dir(nome):
                grupos[chave_nome_pasta_para_mescla(nome)].append(caminho)

        for caminhos in grupos.values():
            caminhos = [caminho for caminho in caminhos if os.path.isdir(caminho)]
            if len(caminhos) <= 1:
                continue

            destino, destino_original = escolher_destino_mescla(caminhos, args.executar)

            for origem in sorted(caminhos, key=lambda caminho: os.path.basename(caminho).casefold()):
                if (
                    caminho_normalizado(origem) == caminho_normalizado(destino)
                    or caminho_normalizado(origem) == caminho_normalizado(destino_original)
                    or not os.path.isdir(origem)
                ):
                    continue
                log(f"[MESCLANDO] {os.path.basename(origem)} -> {os.path.basename(destino)}")
                for item in os.listdir(origem):
                    mover_item_mesclando(os.path.join(origem, item), destino, args.executar)
                if args.executar:
                    try:
                        remover_pasta_vazia_com_historico(origem, executar=True)
                    except OSError:
                        pass
                mescladas += 1

    relatorio(f"RELATORIO - mesclar similares | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    relatorio(f"Pastas analisadas: {len(pais)}")
    relatorio(f"Pastas mescladas/listadas: {mescladas}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")


def comando_mesclar_duas_pastas(args):
    origem = os.path.abspath(args.origem)
    destino = os.path.abspath(args.destino)

    if caminho_normalizado(origem) == caminho_normalizado(destino):
        relatorio("[BLOQUEADO] Origem e destino sao a mesma pasta.")
        return
    if caminho_esta_dentro(destino, origem):
        relatorio("[BLOQUEADO] O destino esta dentro da origem. Isso poderia criar uma mescla infinita.")
        return
    if not os.path.isdir(origem):
        relatorio(f"[ERRO] Origem nao encontrada: {origem}")
        return
    if not os.path.isdir(destino):
        relatorio(f"[ERRO] Destino nao encontrado: {destino}")
        return

    args_origem = criar_args_etapa(args, pasta=origem)
    args_destino = criar_args_etapa(args, pasta=destino)
    if bloquear_pasta_ampla_se_preciso(args_origem, "pastas mesclar origem"):
        return
    if bloquear_pasta_ampla_se_preciso(args_destino, "pastas mesclar destino"):
        return

    log("=== MESCLAR DUAS PASTAS ===")
    log(f"Origem: {origem}")
    log(f"Destino: {destino}")
    if not args.executar:
        log("Modo simulacao: nada sera movido. Use --executar para aplicar de verdade.")
    elif not confirmar("Mesclar origem dentro do destino?", args.sim):
        relatorio("Cancelado.")
        return

    movidos = 0
    erros = 0
    inicio = time.time()
    itens_origem = sorted(os.listdir(origem), key=str.casefold)
    total_itens = len(itens_origem)
    ultimo_progresso = 0
    for indice, nome in enumerate(itens_origem, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=total_itens)
        if mostrar:
            relatorio(texto_progresso("Mesclando itens", indice, total_itens, inicio))
        caminho = os.path.join(origem, nome)
        try:
            mover_item_mesclando(caminho, destino, args.executar)
            movidos += 1
        except OSError as erro:
            erros += 1
            log(f"[ERRO] {caminho_curto(caminho)}: {erro}")

    if args.executar:
        try:
            if os.path.isdir(origem) and not os.listdir(origem):
                remover_pasta_vazia_com_historico(origem, executar=True)
        except OSError:
            pass

    relatorio(f"RELATORIO - mesclar duas pastas | {nome_alvo(destino)}", respiro=True)
    relatorio(f"Origem: {origem}")
    relatorio(f"Destino: {destino}")
    relatorio(f"Itens movidos/listados: {movidos}")
    relatorio(f"Erros: {erros}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")


def criar_args_etapa(args, **opcoes):
    valores = vars(args).copy()
    valores.update(opcoes)
    return argparse.Namespace(**valores)



