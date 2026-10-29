import os
import time

from maestro import *


# =============================================================================
# Organizar arquivos gerais por tipo/extensao
# =============================================================================


def tipo_do_arquivo(nome):
    extensao = os.path.splitext(nome)[1].strip().lstrip(".")
    if not extensao:
        return "SEM_EXTENSAO"
    return extensao.upper()


def pasta_tipo_disponivel(pasta_atual, tipo):
    destino = os.path.join(pasta_atual, tipo)
    if not os.path.exists(destino) or os.path.isdir(destino):
        return destino

    base = os.path.join(pasta_atual, f"{tipo}_ARQUIVOS")
    destino = base
    contador = 1
    while os.path.exists(destino) and not os.path.isdir(destino):
        destino = f"{base}_{contador}"
        contador += 1
    return destino


def destino_por_tipo(pasta_atual, nome):
    tipo = tipo_do_arquivo(nome)
    pasta_nome = normalizar_nome(os.path.basename(pasta_atual))
    if pasta_nome in {normalizar_nome(tipo), normalizar_nome(f"{tipo}_ARQUIVOS")}:
        return None, tipo
    return os.path.join(pasta_tipo_disponivel(pasta_atual, tipo), nome), tipo


def iterar_arquivos_para_tipo(raiz, incluir_subpastas):
    if incluir_subpastas:
        for pasta_atual, subpastas, arquivos in os.walk(raiz, topdown=True):
            subpastas[:] = [
                subpasta
                for subpasta in subpastas
                if not ignorar_dir(subpasta) and normalizar_nome(subpasta) != normalizar_nome(tipo_do_arquivo(subpasta))
            ]
            yield pasta_atual, arquivos
        return

    try:
        nomes = sorted(os.listdir(raiz), key=str.casefold)
    except OSError as erro:
        raise erro
    yield raiz, nomes


def comando_organizar_tipos(args):
    if bloquear_pasta_ampla_se_preciso(args, "pastas organizar-tipos"):
        return

    raiz = os.path.abspath(args.pasta)
    inicio = time.time()
    if not os.path.isdir(raiz):
        relatorio(f"[ERRO] Pasta nao encontrada: {raiz}")
        return

    incluir_subpastas = bool(getattr(args, "subpastas", False))
    candidatos = []
    tipos = {}
    arquivos_analisados = 0

    try:
        for pasta_atual, nomes in iterar_arquivos_para_tipo(raiz, incluir_subpastas):
            for nome in sorted(nomes, key=str.casefold):
                caminho = os.path.join(pasta_atual, nome)
                if not os.path.isfile(caminho):
                    continue
                if nome.casefold() in ARQUIVOS_SISTEMA_IGNORADOS_PASTA_VAZIA:
                    continue
                arquivos_analisados += 1
                destino_base, tipo = destino_por_tipo(pasta_atual, nome)
                if destino_base is None:
                    continue
                destino = gerar_caminho_unico(destino_base)
                if caminho_normalizado(caminho) == caminho_normalizado(destino):
                    continue
                candidatos.append((caminho, destino, tipo))
                tipos[tipo] = tipos.get(tipo, 0) + 1
    except OSError as erro:
        relatorio(f"[ERRO] Nao consegui listar a pasta: {raiz} ({erro})")
        return

    acao = "selecionados para mover" if args.executar else "que seriam movidos"
    escopo = "pasta e subpastas" if incluir_subpastas else "somente arquivos soltos da pasta escolhida"
    tipos_resumo = ", ".join(f"{tipo}: {quantidade}" for tipo, quantidade in sorted(tipos.items()))

    relatorio(f"RELATORIO - organizar por tipo | {nome_alvo(raiz)}", respiro=True)
    relatorio(f"Pasta: {raiz}")
    relatorio("Regra: cria pastas por extensao, como PDF, PNG, JPG e DOCX.")
    relatorio(f"Escopo: {escopo}")
    relatorio(f"Arquivos analisados: {arquivos_analisados}")
    relatorio(f"Arquivos {acao}: {len(candidatos)}")
    relatorio(f"Tipos envolvidos: {tipos_resumo if tipos_resumo else 'nenhum'}")

    if not candidatos:
        if not incluir_subpastas:
            relatorio("Se os arquivos estiverem dentro de subpastas, use --subpastas.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not args.executar:
        relatorio("Nada foi movido. Use --executar --sim para aplicar.")
        relatorio(f"Tempo: {formatar_tempo(time.time() - inicio)}")
        return

    if not confirmar(f"Mover {len(candidatos)} arquivo(s) para pastas por tipo?", args.sim):
        relatorio("Cancelado.")
        return

    movidos = 0
    erros = 0
    ultimo_progresso = 0
    total = len(candidatos)
    for indice, (origem, destino, _) in enumerate(candidatos, start=1):
        mostrar, ultimo_progresso = deve_mostrar_progresso(indice, ultimo_progresso, lote=100, total=total)
        if mostrar:
            relatorio(texto_progresso("Organizando por tipo", indice, total, inicio))
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


