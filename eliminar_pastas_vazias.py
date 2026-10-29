import os
import time
from pathlib import Path

from maestro import *


# =============================================================================
# Remover pastas vazias
# =============================================================================


def encontrar_pastas_vazias_em_cascata(raiz, inicio_varredura):
    raiz_norm = caminho_normalizado(raiz)
    todas = []
    apagavel_por_pasta = {}
    ultimo_progresso = 0

    for pasta_atual, subpastas, arquivos in os.walk(raiz, topdown=True):
        subpastas_ignoradas = [subpasta for subpasta in subpastas if ignorar_dir(subpasta)]
        subpastas[:] = [subpasta for subpasta in subpastas if not ignorar_dir(subpasta)]
        todas.append(pasta_atual)

        arquivos_reais = [
            arquivo
            for arquivo in arquivos
            if arquivo.casefold() not in ARQUIVOS_SISTEMA_IGNORADOS_PASTA_VAZIA
        ]
        pasta_norm = caminho_normalizado(pasta_atual)
        apagavel_por_pasta[pasta_norm] = not arquivos_reais and not subpastas_ignoradas

        mostrar, ultimo_progresso = deve_mostrar_progresso(len(todas), ultimo_progresso, lote=500)
        if mostrar:
            relatorio(texto_progresso("Analisando pastas vazias", len(todas), None, inicio_varredura))

    for pasta in reversed(todas):
        pasta_norm = caminho_normalizado(pasta)
        if not apagavel_por_pasta.get(pasta_norm, False):
            continue
        try:
            filhos = [
                caminho_normalizado(os.path.join(pasta, nome))
                for nome in os.listdir(pasta)
                if os.path.isdir(os.path.join(pasta, nome)) and not ignorar_dir(nome)
            ]
        except OSError:
            apagavel_por_pasta[pasta_norm] = False
            continue
        if any(not apagavel_por_pasta.get(filho, False) for filho in filhos):
            apagavel_por_pasta[pasta_norm] = False

    return [
        Path(pasta)
        for pasta in todas
        if caminho_normalizado(pasta) != raiz_norm and apagavel_por_pasta.get(caminho_normalizado(pasta), False)
    ]


def comando_pastas_vazias(args):

    raiz = os.path.abspath(args.pasta)
    inicio = time.time()
    inicio_varredura = time.time()
    vazias = encontrar_pastas_vazias_em_cascata(raiz, inicio_varredura)
    log(f"\nPastas vazias encontradas: {len(vazias)}")
    for pasta in vazias[:200]:
        log(f"[VAZIA] {pasta}")
    if len(vazias) > 200:
        log(f"... mais {len(vazias) - 200} pasta(s)")

    if not args.deletar:
        relatorio(f"RELATORIO - pastas vazias | {nome_alvo(raiz)}", respiro=True)
        relatorio(f"Pasta: {raiz}")
        relatorio(f"Pastas vazias encontradas: {len(vazias)}")
        relatorio("Nada foi deletado. Use --deletar --executar para remover.")
        return
    if not args.executar:
        relatorio(f"RELATORIO - pastas vazias | {nome_alvo(raiz)}", respiro=True)
        relatorio(f"Pasta: {raiz}")
        relatorio(f"Pastas vazias que seriam removidas: {len(vazias)}")
        return
    if not confirmar(f"Deletar {len(vazias)} pastas vazias?", args.sim):
        relatorio("Cancelado.")
        return

    removidas = 0
    erros = 0
    total_vazias = len(vazias)
    ultimo_progresso = 0
    for indice, pasta in enumerate(sorted(vazias, key=lambda caminho: str(caminho).count(os.sep), reverse=True), start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=total_vazias)
        if mostrar:
            relatorio(texto_progresso("Removendo pastas vazias", indice, total_vazias, inicio))
        try:
            if pasta.exists():
                for arquivo_sistema in ARQUIVOS_SISTEMA_IGNORADOS_PASTA_VAZIA:
                    caminho_sistema = pasta / arquivo_sistema
                    if caminho_sistema.exists() and caminho_sistema.is_file():
                        apagar_arquivo_com_historico(caminho_sistema, executar=True)
                remover_pasta_vazia_com_historico(pasta, executar=True)
                removidas += 1
        except OSError as erro:
            erros += 1
            log(f"[IGNORADA] Nao estava vazia ou sem permissao: {pasta} ({erro})")
    relatorio(f"RELATORIO - pastas vazias | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    relatorio(f"Pastas vazias removidas: {removidas}")
    relatorio(f"Erros/ignoradas: {erros}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")


def comando_limpar_pastas(args):

    args.deletar = True
    return comando_pastas_vazias(args)

