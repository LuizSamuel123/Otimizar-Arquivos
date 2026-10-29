import os
import time

from maestro import *


# =============================================================================
# Dissolver pastas
# =============================================================================


def encontrar_itens_para_dissolver(raiz):
    arquivos = []
    pastas = []
    inicio = time.time()
    ultimo_progresso = 0
    analisadas = 0

    for pasta_atual, subpastas, nomes_arquivos in os.walk(raiz, topdown=True):
        analisadas += 1
        mostrar, ultimo_progresso = deve_mostrar_progresso(analisadas, ultimo_progresso, lote=500)
        if mostrar:
            relatorio(texto_progresso("Mapeando dissolucao", analisadas, None, inicio))

        subpastas[:] = [subpasta for subpasta in subpastas if not ignorar_dir(subpasta)]
        if caminho_normalizado(pasta_atual) != caminho_normalizado(raiz):
            pastas.append(pasta_atual)

        for nome in sorted(nomes_arquivos, key=str.casefold):
            caminho = os.path.join(pasta_atual, nome)
            if not os.path.isfile(caminho):
                continue
            if caminho_normalizado(pasta_atual) == caminho_normalizado(raiz):
                continue
            arquivos.append(caminho)

    return arquivos, pastas


def comando_dissolver(args):
    if bloquear_pasta_ampla_se_preciso(args, "pastas dissolver"):
        return

    raiz = os.path.abspath(args.pasta)
    inicio = time.time()
    if not os.path.isdir(raiz):
        relatorio(f"[ERRO] Pasta nao encontrada: {raiz}")
        return

    arquivos, pastas = encontrar_itens_para_dissolver(raiz)
    candidatos = []
    tipos = {}
    total_bytes = 0

    for origem in arquivos:
        nome = os.path.basename(origem)
        destino = gerar_caminho_unico(os.path.join(raiz, nome))
        candidatos.append((origem, destino))
        extensao = os.path.splitext(nome)[1].strip().lstrip(".").upper() or "SEM_EXTENSAO"
        tipos[extensao] = tipos.get(extensao, 0) + 1
        try:
            total_bytes += os.path.getsize(origem)
        except OSError:
            pass

    acao = "movidos" if args.executar else "que seriam movidos"
    tipos_resumo = ", ".join(f"{tipo}: {quantidade}" for tipo, quantidade in sorted(tipos.items()))

    relatorio(f"RELATORIO - dissolucao | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta mae: {raiz}")
    relatorio("Regra: move todos os arquivos das subpastas para a pasta mae escolhida.")
    relatorio(f"Subpastas analisadas: {len(pastas)}")
    relatorio(f"Arquivos {acao}: {len(candidatos)}")
    relatorio(f"Tamanho estimado: {formatar_bytes(total_bytes)}")
    relatorio(f"Tipos envolvidos: {tipos_resumo if tipos_resumo else 'nenhum'}")

    if not candidatos and not pastas:
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not args.executar:
        relatorio("Nada foi movido. Use --executar --sim para aplicar.")
        relatorio("Depois de mover, as subpastas vazias tambem seriam removidas.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not confirmar(f"Dissolver {len(pastas)} subpasta(s) e mover {len(candidatos)} arquivo(s)?", args.sim):
        relatorio("Cancelado.")
        return

    movidos = 0
    erros = 0
    ultimo_progresso = 0
    total = len(candidatos)
    for indice, (origem, destino) in enumerate(candidatos, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=total)
        if mostrar:
            relatorio(texto_progresso("Dissolvendo arquivos", indice, total, inicio))
        try:
            destino_final = gerar_caminho_unico(os.path.join(raiz, os.path.basename(origem)))
            mover_com_historico(origem, destino_final, executar=True)
            movidos += 1
        except OSError as erro:
            erros += 1
            log(f"[ERRO] {origem} -> {destino} ({erro})")

    pastas_removidas = 0
    erros_pastas = 0
    for pasta in sorted(pastas, key=lambda caminho: caminho.count(os.sep), reverse=True):
        try:
            if os.path.isdir(pasta) and not os.listdir(pasta):
                remover_pasta_vazia_com_historico(pasta, executar=True)
                pastas_removidas += 1
        except OSError as erro:
            erros_pastas += 1
            log(f"[IGNORADA] Nao consegui remover pasta: {pasta} ({erro})")

    relatorio(f"Arquivos movidos: {movidos}")
    relatorio(f"Pastas vazias removidas: {pastas_removidas}")
    relatorio(f"Erros ao mover arquivos: {erros}")
    relatorio(f"Erros/ignoradas ao remover pastas: {erros_pastas}")
    relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
