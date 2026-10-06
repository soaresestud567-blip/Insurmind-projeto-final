import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from services.database import init_db, list_policies, get_policy
from pipeline import PolicyPipeline
from agents.comparison_agent import ComparisonAgent
from agents.report_agent import ReportAgent


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Inteligência de Apólices D&O",
    page_icon="🛡️",
    layout="wide"
)

init_db()

def classify_processing_error(error):
    """
    Converte exceções técnicas em mensagens adequadas
    para exibição na interface.
    """

    message = str(error)
    lower = message.lower()

    # Limite gratuito / rate limit
    if (
        "cota diária gratuita" in lower
        or "free-models-per-day" in lower
        or (
            "429" in message
            and "rate limit" in lower
        )
    ):
        return {
            "tipo": "rate_limit",
            "titulo": "Limite diário gratuito atingido",
            "mensagem": (
                "A cota gratuita da IA está temporariamente "
                "indisponível."
            ),
        }

    # Tesseract / OCR
    if (
        "tesseract" in lower
        or "pytesseract" in lower
        or "tessdata" in lower
    ):
        return {
            "tipo": "ocr",
            "titulo": "Falha no OCR",
            "mensagem": (
                "Não foi possível executar o reconhecimento de texto. "
                "Verifique se o Tesseract está instalado e se o caminho "
                "TESSERACT_CMD está configurado corretamente no .env."
            ),
        }

    # Documento sem texto suficiente
    if (
        "texto suficiente" in lower
        or "não foi possível extrair texto" in lower
        or "nao foi possivel extrair texto" in lower
    ):
        return {
            "tipo": "sem_texto",
            "titulo": "Texto insuficiente",
            "mensagem": (
                "O documento não forneceu texto suficiente para análise. "
                "Verifique se o arquivo está legível e tente novamente."
            ),
        }

    # Chave/configuração OpenRouter
    if (
        "openrouter_api_key" in lower
        or "api key" in lower
        or "api_key" in lower
    ):
        return {
            "tipo": "configuracao",
            "titulo": "Configuração da IA incompleta",
            "mensagem": (
                "A configuração de acesso à IA não foi encontrada. "
                "Verifique o arquivo .env."
            ),
        }

    # Modelo bloqueado
    if "modelo bloqueado" in lower:
        return {
            "tipo": "configuracao",
            "titulo": "Modelo não permitido",
            "mensagem": (
                "O projeto está configurado para utilizar somente "
                "o modelo gratuito openrouter/free."
            ),
        }

    # Arquivo/formato inválido
    if (
        "formato" in lower
        or "extensão" in lower
        or "extensao" in lower
        or "arquivo inválido" in lower
        or "arquivo invalido" in lower
    ):
        return {
            "tipo": "arquivo",
            "titulo": "Arquivo não suportado",
            "mensagem": (
                "O documento não pôde ser processado. "
                "Utilize PDF, PNG, JPG, JPEG, TIF ou TIFF."
            ),
        }

    # Demais erros
    return {
        "tipo": "inesperado",
        "titulo": "Falha no processamento",
        "mensagem": (
            "O documento não pôde ser processado devido a um erro "
            "inesperado. Verifique o terminal para obter os detalhes "
            "técnicos."
        ),
    }


# ============================================================
# FUNÇÃO PARA EXIBIR UMA APÓLICE
# ============================================================

def show_policy_analysis(data):

    # ========================================================
    # IDENTIFICAÇÃO DO TIPO DE DOCUMENTO
    # ========================================================

    tipo_documento = (
        data.get("tipo_documento")
        or "Não identificado"
    )

    ramo_seguro = (
        data.get("ramo_seguro")
        or "Não identificado"
    )

    st.markdown("## 📋 Resumo da análise")


    st.markdown(
        f"### 📑 Tipo de documento: **{tipo_documento}**"
    )

    st.markdown(
        f"### 🛡️ Ramo identificado: **{ramo_seguro}**"
    )

    if ramo_seguro == "Seguro Viagem":
        st.warning(
            "O documento analisado foi identificado como **Seguro Viagem** "
            "e não aparenta pertencer ao ramo **D&O**. "
            "A extração foi realizada, mas as funcionalidades deste MVP "
            "foram desenvolvidas especificamente para documentos D&O."
        )

    elif ramo_seguro == "Não identificado":
        st.info(
            "Não foi possível confirmar automaticamente que este documento "
            "pertence ao ramo D&O. Recomenda-se verificar o documento original."
        )

    # --------------------------------------------------------
    # Avisos contextuais conforme o tipo do documento
    # --------------------------------------------------------

    if tipo_documento == "Condições Gerais":

        st.warning(
            "Este documento foi identificado como **Condições Gerais**. "
            "Ele apresenta regras, definições, coberturas, exclusões e "
            "condições do produto, mas não necessariamente contém os "
            "dados individualizados de uma apólice contratada."
        )

        st.info(
            "ℹ️ Campos como **segurado, número da apólice, limite "
            "contratado, limite agregado, franquia, prêmio e vigência** "
            "podem aparecer como **Não identificado** quando essas "
            "informações dependem da Especificação da Apólice."
        )

    elif tipo_documento == "Especificação / Apólice":

        st.success(
            "Este documento foi identificado como uma "
            "**Especificação / Apólice** e pode conter dados "
            "individualizados da contratação."
        )

    elif tipo_documento == "Apólice / Documento individualizado":

        st.success(
            "Foram identificados dados individualizados suficientes "
            "para caracterizar este documento como uma "
            "**apólice ou documento individualizado**."
        )

    elif tipo_documento == "Endosso":

        st.info(
            "Este documento foi identificado como **Endosso**. "
            "As informações apresentadas podem alterar ou complementar "
            "uma apólice existente e devem ser interpretadas em conjunto "
            "com os demais documentos contratuais."
        )

    else:

        st.info(
            "O sistema não conseguiu determinar com segurança o tipo "
            "deste documento. Os dados abaixo foram mantidos conforme "
            "identificados na análise."
        )

    st.divider()

    # --------------------------------------------------------
    # Cards principais
    # --------------------------------------------------------
    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Seguradora",
            data.get("seguradora") or "Não identificado"
        )

    with c2:
        st.metric(
            "Nº da apólice",
            data.get("numero_apolice") or "Não identificado"
        )

    st.markdown("#### 💰 Valores principais")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Limite de responsabilidade**")
        st.info(
            str(
                data.get("limite_responsabilidade")
                or "Não identificado"
            )
        )

    with c2:
        st.markdown("**Franquia / Retenção**")
        st.info(
            str(
                data.get("franquia")
                or "Não identificado"
            )
        )
    

    st.divider()

    # --------------------------------------------------------
    # Informações gerais
    # --------------------------------------------------------

    st.markdown("### 🏢 Informações gerais")

    c1, c2 = st.columns(2)

    with c1:

        st.markdown(
            f"**Segurado:**  \n"
            f"{data.get('segurado') or 'Não identificado'}"
        )

        st.markdown(
            f"**Moeda:**  \n"
            f"{data.get('moeda') or 'Não identificado'}"
        )

        st.markdown(
            f"**Prêmio:**  \n"
            f"{data.get('premio') or 'Não identificado'}"
        )

    with c2:

        st.markdown(
            f"**Início da vigência:**  \n"
            f"{data.get('vigencia_inicio') or 'Não identificado'}"
        )

        st.markdown(
            f"**Fim da vigência:**  \n"
            f"{data.get('vigencia_fim') or 'Não identificado'}"
        )

        st.markdown(
            f"**Limite agregado:**  \n"
            f"{data.get('limite_agregado') or 'Não identificado'}"
        )

    st.divider()

    # --------------------------------------------------------
    # Função auxiliar para itens contratuais
    # --------------------------------------------------------

    def show_items(title, icon, items):

        st.markdown(f"### {icon} {title}")

        if not items:
            st.info("Nenhuma informação identificada.")
            return

        for i, item in enumerate(items, start=1):

            if isinstance(item, dict):

                name = (
                    item.get("nome")
                    or f"Item {i}"
                )

                description = (
                    item.get("descricao")
                    or "Sem descrição."
                )

                page = item.get("pagina")

                evidence = (
                    item.get("evidencia_textual")
                    or item.get("trecho")
                )

                label = f"{i}. {name}"

                if page:
                    label += f"  •  pág. {page}"

                with st.expander(label):

                    st.write(description)

                    if page:
                        st.caption(
                            f"📄 Página: {page}"
                        )

                    if evidence:

                        st.markdown(
                            "**Evidência documental:**"
                        )

                        st.info(evidence)

            else:

                st.write(f"• {item}")

    # --------------------------------------------------------
    # Conteúdo contratual
    # --------------------------------------------------------

    coberturas = data.get("coberturas", []) or []
    exclusoes = data.get("exclusoes", []) or []
    extensoes = data.get("extensoes", []) or []
    definicoes = data.get("definicoes_relevantes", []) or []
    clausulas = data.get("clausulas_relevantes", []) or []

    tab_cob, tab_exc, tab_ext, tab_def, tab_cla = st.tabs([
        f"🛡️ Coberturas ({len(coberturas)})",
        f"🚫 Exclusões ({len(exclusoes)})",
        f"➕ Extensões ({len(extensoes)})",
        f"📖 Definições ({len(definicoes)})",
        f"📑 Cláusulas ({len(clausulas)})"
    ])

    with tab_cob:
        show_items(
            "Coberturas",
            "🛡️",
            coberturas
        )

    with tab_exc:
        show_items(
            "Exclusões",
            "🚫",
            exclusoes
        )

    with tab_ext:
        show_items(
            "Extensões",
            "➕",
            extensoes
        )

    with tab_def:
        show_items(
            "Definições relevantes",
            "📖",
            definicoes
        )

    with tab_cla:
        show_items(
            "Cláusulas relevantes",
            "📑",
            clausulas
        )

    # --------------------------------------------------------
    # Observações
    # --------------------------------------------------------

    observations = data.get("observacoes")

    if observations:

        st.divider()

        st.markdown(
            "### ⚠️ Observações da análise"
        )

        if not isinstance(observations, list):
            observations = [observations]

        for i, observation in enumerate(
            observations,
            start=1
        ):

            # Observação estruturada
            if isinstance(observation, dict):

                name = (
                    observation.get("nome")
                    or f"Observação {i}"
                )

                description = (
                    observation.get("descricao")
                    or observation.get("valor")
                    or "Sem descrição."
                )

                page = observation.get("pagina")

                evidence = (
                    observation.get("evidencia_textual")
                    or observation.get("trecho")
                )

                label = f"⚠️ {name}"

                if page:
                    label += f"  •  pág. {page}"

                with st.expander(label):

                    st.write(description)

                    if page:
                        st.caption(
                            f"📄 Página: {page}"
                        )

                    if evidence:

                        st.markdown(
                            "**Evidência documental:**"
                        )

                        st.info(evidence)

            # Observação simples
            else:

                st.warning(
                    str(observation)
                )

    # --------------------------------------------------------
    # Evidências documentais
    # --------------------------------------------------------

    evidences = data.get(
        "evidencias",
        []
    ) or []

    if evidences:

        st.divider()

        st.markdown(
            "### 🔎 Evidências documentais"
        )

        rows = []

        for evidence in evidences:

            if isinstance(evidence, dict):

                rows.append({
                    "Campo":
                        evidence.get("campo"),

                    "Valor":
                        evidence.get("valor"),

                    "Página":
                        evidence.get("pagina"),

                    "Trecho":
                        evidence.get("trecho")
                })

        if rows:

            df_evidences = pd.DataFrame(rows)

            # Normaliza as colunas para texto.
            # Evita conflito de tipos no PyArrow/Streamlit,
            # especialmente quando "Página" mistura int e str.
            for column in df_evidences.columns:
                df_evidences[column] = (
                    df_evidences[column]
                    .fillna("")
                    .astype(str)
                )

            st.dataframe(
                df_evidences,
                width="stretch",
                hide_index=True
            )

    # --------------------------------------------------------
    # JSON técnico
    # --------------------------------------------------------

    st.divider()

    with st.expander(
        "🔧 Dados técnicos / JSON"
    ):

        st.json(data)

def show_comparison_result(comp, a, b):

    st.markdown("## ⚖️ Comparação D&O")

    # =====================================================
    # STATUS DA COMPARAÇÃO
    # =====================================================

    modo = comp.get(
        "modo_comparacao",
        "desconhecido"
    )

    ia_disponivel = comp.get(
        "analise_ia_disponivel",
        False
    )

    if modo == "hibrido" and ia_disponivel:

        st.success(
            "🟢 **Comparação híbrida completa** — "
            "os campos objetivos foram comparados localmente "
            "e o conteúdo contratual foi analisado por IA."
        )

    elif modo == "local":

        st.warning(
            "🟡 **Comparação local** — "
            "os campos objetivos foram comparados normalmente, "
            "mas a análise semântica de coberturas, exclusões, "
            "extensões e cláusulas por IA não está disponível "
            "neste momento."
        )

    else:

        st.info(
            "ℹ️ **Modo de comparação não identificado.**"
        )

    # =====================================================
    # APÓLICES COMPARADAS
    # =====================================================

    a_data = a["structured"]
    b_data = b["structured"]

    col_a, col_b = st.columns(2)

    # -----------------------------------------------------
    # APÓLICE A
    # -----------------------------------------------------

    with col_a:

        st.markdown("### 🅰️ Apólice A")

        st.markdown(
            f"**{a_data.get('seguradora') or a['filename']}**"
        )

        st.caption(a["filename"])

        st.markdown(
            "**Limite de responsabilidade**"
        )

        st.info(
            str(
                a_data.get(
                    "limite_responsabilidade"
                )
                or "Não identificado"
            )
        )

        st.markdown(
            "**Franquia / Retenção**"
        )

        st.info(
            str(
                a_data.get("franquia")
                or "Não identificado"
            )
        )

        st.write(
            "**Vigência:** "
            f"{a_data.get('vigencia_inicio') or '?'} "
            "→ "
            f"{a_data.get('vigencia_fim') or '?'}"
        )

    # -----------------------------------------------------
    # APÓLICE B
    # -----------------------------------------------------

    with col_b:

        st.markdown("### 🅱️ Apólice B")

        st.markdown(
            f"**{b_data.get('seguradora') or b['filename']}**"
        )

        st.caption(b["filename"])

        st.markdown(
            "**Limite de responsabilidade**"
        )

        st.info(
            str(
                b_data.get(
                    "limite_responsabilidade"
                )
                or "Não identificado"
            )
        )

        st.markdown(
            "**Franquia / Retenção**"
        )

        st.info(
            str(
                b_data.get("franquia")
                or "Não identificado"
            )
        )

        st.write(
            "**Vigência:** "
            f"{b_data.get('vigencia_inicio') or '?'} "
            "→ "
            f"{b_data.get('vigencia_fim') or '?'}"
        )

    st.divider()

    # =====================================================
    # RESUMO EXECUTIVO
    # =====================================================

    st.markdown(
        "### 📝 Resumo executivo"
    )

    resumo = comp.get(
        "resumo_executivo"
    )

    if resumo:

        st.info(resumo)

    else:

        st.info(
            "Nenhum resumo executivo foi produzido."
        )

    # =====================================================
    # DIFERENÇAS
    # =====================================================

    st.markdown(
        "### 🔎 Diferenças identificadas"
    )

    differences = (
        comp.get(
            "diferencas",
            []
        )
        or []
    )

    if not differences:

        st.success(
            "Nenhuma diferença relevante "
            "foi identificada."
        )

    else:

        # -------------------------------------------------
        # Ordenação por relevância
        # -------------------------------------------------

        priority = {
            "alto": 0,
            "alta": 0,

            "medio": 1,
            "médio": 1,
            "media": 1,
            "média": 1,

            "baixo": 2,
            "baixa": 2
        }

        differences = sorted(
            differences,
            key=lambda x: priority.get(
                str(
                    x.get(
                        "impacto",
                        ""
                    )
                ).lower(),
                3
            )
        )

        # -------------------------------------------------
        # Exibição das diferenças
        # -------------------------------------------------

        for difference in differences:

            category = (
                difference.get(
                    "categoria"
                )
                or "Diferença"
            )

            impact = str(
                difference.get(
                    "impacto"
                )
                or "não classificado"
            )

            impact_lower = (
                impact.lower()
            )

            # ---------------------------------------------
            # Relevância alta
            # ---------------------------------------------

            if impact_lower in [
                "alto",
                "alta"
            ]:

                icon = "🔴"
                relevance = "ALTA"

            # ---------------------------------------------
            # Relevância média
            # ---------------------------------------------

            elif impact_lower in [
                "medio",
                "médio",
                "media",
                "média"
            ]:

                icon = "🟠"
                relevance = "MÉDIA"

            # ---------------------------------------------
            # Relevância baixa
            # ---------------------------------------------

            elif impact_lower in [
                "baixo",
                "baixa"
            ]:

                icon = "🟢"
                relevance = "BAIXA"

            # ---------------------------------------------
            # Não classificado
            # ---------------------------------------------

            else:

                icon = "⚪"
                relevance = (
                    impact.upper()
                )

            # ---------------------------------------------
            # Card da diferença
            # ---------------------------------------------

            with st.expander(
                f"{icon} {relevance} • {category}",
                expanded=(
                    relevance == "ALTA"
                )
            ):

                col1, col2 = (
                    st.columns(2)
                )

                # Apólice A
                with col1:

                    st.markdown(
                        "##### 🅰️ Apólice A"
                    )

                    st.write(
                        difference.get(
                            "apolice_a"
                        )
                        or "Não informado"
                    )

                # Apólice B
                with col2:

                    st.markdown(
                        "##### 🅱️ Apólice B"
                    )

                    st.write(
                        difference.get(
                            "apolice_b"
                        )
                        or "Não informado"
                    )

                comentario = (
                    difference.get(
                        "comentario"
                    )
                )

                if comentario:

                    st.markdown(
                        "**Análise comparativa:**"
                    )

                    st.write(
                        comentario
                    )

                # -----------------------------------------
                # Origem da comparação
                # -----------------------------------------

                origem = difference.get(
                    "origem"
                )

                if origem == "comparacao_local":

                    st.caption(
                        "⚙️ Diferença identificada "
                        "automaticamente pelo comparador local."
                    )

                elif origem:

                    st.caption(
                        "🤖 Diferença identificada "
                        "durante a análise semântica."
                    )

    # =====================================================
    # PONTOS DE ATENÇÃO + SIMILARIDADES
    # =====================================================

    st.divider()

    attention = (
        comp.get(
            "pontos_atencao",
            []
        )
        or []
    )

    similarities = (
        comp.get(
            "similaridades_relevantes",
            []
        )
        or []
    )

    col_attention, col_similarities = (
        st.columns(2)
    )

    # -----------------------------------------------------
    # Pontos de atenção
    # -----------------------------------------------------

    with col_attention:

        st.markdown(
            "### ⚠️ Pontos de atenção"
        )

        if attention:

            for item in attention:

                if isinstance(
                    item,
                    dict
                ):

                    texto = (
                        item.get("descricao")
                        or item.get("texto")
                        or item.get("valor")
                        or str(item)
                    )

                    st.warning(
                        texto
                    )

                else:

                    st.warning(
                        str(item)
                    )

        else:

            st.info(
                "Nenhum ponto de atenção "
                "foi identificado."
            )

    # -----------------------------------------------------
    # Similaridades
    # -----------------------------------------------------

    with col_similarities:

        st.markdown(
            "### 🤝 Similaridades relevantes"
        )

        if similarities:

            for item in similarities:

                if isinstance(
                    item,
                    dict
                ):

                    texto = (
                        item.get("descricao")
                        or item.get("texto")
                        or item.get("valor")
                        or str(item)
                    )

                    st.success(
                        texto
                    )

                else:

                    st.success(
                        str(item)
                    )

        else:

            # Quando a IA não participou, não afirmamos
            # que não existem similaridades.
            if not ia_disponivel:

                st.info(
                    "A identificação de similaridades "
                    "contratuais depende da análise "
                    "semântica por IA, que não foi "
                    "executada nesta comparação."
                )

            else:

                st.info(
                    "Nenhuma similaridade relevante "
                    "foi destacada."
                )

# ============================================================
# CABEÇALHO
# ============================================================

st.title("🛡️ Inteligência de Apólices D&O")

st.caption(
    "MVP para extração, estruturação, consulta e "
    "comparação inteligente de apólices D&O."
)


# ============================================================
# ABAS PRINCIPAIS
# ============================================================

tab1, tab2, tab3 = st.tabs([
    "📄 Analisar documentos",
    "🗃️ Consultar apólices",
    "⚖️ Comparar"
])


# ============================================================
# ABA 1 — ANÁLISE
# ============================================================

with tab1:

    st.subheader(
        "1. Recebimento e análise"
    )

    st.write(
        "Envie uma ou mais apólices em PDF ou imagem. "
        "O sistema extrairá o texto, identificará as "
        "informações relevantes e armazenará os "
        "resultados na base estruturada."
    )

    uploads = st.file_uploader(
        "Envie PDF ou imagem",
        type=[
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "tif",
            "tiff"
        ],
        accept_multiple_files=True
    )

    if st.button(
        "Processar documentos",
        type="primary",
        disabled=not uploads
    ):

        pipe = PolicyPipeline()

        for f in uploads:

            st.divider()

            st.markdown(
                f"### 📄 {f.name}"
            )

            progress_bar = st.progress(
                0,
                text="Preparando processamento..."
            )

            progress_text = st.empty()
            detail_text = st.empty()

            # ------------------------------------------------
            # Callback de progresso
            # ------------------------------------------------

            def update_progress(
                stage,
                completed,
                total,
                message
            ):

                # Recepção
                if stage == "recepcao":

                    progress_bar.progress(
                        5,
                        text="Recebendo documento..."
                    )

                    progress_text.write(
                        "📥 Recebendo documento..."
                    )

                # OCR / texto
                elif stage == "ocr":

                    if completed == 0:

                        progress_bar.progress(
                            10,
                            text="Extraindo texto..."
                        )

                        progress_text.write(
                            "📖 Extraindo texto "
                            "do documento..."
                        )

                    else:

                        progress_bar.progress(
                            20,
                            text="Texto extraído."
                        )

                        progress_text.write(
                            "✅ Texto extraído "
                            "com sucesso."
                        )

                # IA
                elif stage == "ia":

                    if total > 0:

                        fraction = (
                            completed / total
                        )

                        # IA ocupa 20% até 85%
                        percent = int(
                            20 + (
                                fraction * 65
                            )
                        )

                        percent = min(
                            max(percent, 20),
                            85
                        )

                        # Consolidação
                        if (
                            "Consolidando"
                            in message
                        ):

                            progress_bar.progress(
                                85,
                                text=(
                                    "Consolidando "
                                    "resultados..."
                                )
                            )

                            progress_text.write(
                                "🧠 Consolidando "
                                "resultados da análise..."
                            )

                            detail_text.write(
                                f"Todos os {total} "
                                f"blocos foram analisados."
                            )

                        # Blocos normais
                        else:

                            progress_bar.progress(
                                percent,
                                text=(
                                    f"Analisando blocos: "
                                    f"{completed}/{total}"
                                )
                            )

                            progress_text.write(
                                "🤖 Analisando "
                                "documento com IA..."
                            )

                            detail_text.write(
                                f"Blocos concluídos: "
                                f"{completed} / {total}"
                            )

                # Estruturação
                elif stage == "estrutura":

                    progress_bar.progress(
                        90,
                        text=(
                            "Estruturando "
                            "informações..."
                        )
                    )

                    progress_text.write(
                        "🧩 Estruturando "
                        "informações..."
                    )

                # Banco
                elif stage == "banco":

                    progress_bar.progress(
                        95,
                        text=(
                            "Salvando na base..."
                        )
                    )

                    progress_text.write(
                        "💾 Salvando apólice "
                        "na base..."
                    )

                # Concluído
                elif stage == "concluido":

                    progress_bar.progress(
                        100,
                        text=(
                            "Análise concluída."
                        )
                    )

                    progress_text.write(
                        "✅ Análise concluída."
                    )

                    detail_text.empty()

            # ------------------------------------------------
            # Processamento
            # ------------------------------------------------

            try:

                pid, data = pipe.process(
                    f,
                    progress_callback=update_progress
                )

                st.success(
                    f"{f.name} concluído "
                    f"com sucesso — ID {pid}"
                )

                show_policy_analysis(
                    data
                )

            except Exception as e:

                error_info = classify_processing_error(e)

                # Registra o erro técnico somente no terminal.
                print(
                    f"[ERRO] Falha ao processar {f.name}: "
                    f"{type(e).__name__}: {e}"
                )

                # ------------------------------------------------
                # Limite diário gratuito
                # ------------------------------------------------

                if error_info["tipo"] == "rate_limit":

                    progress_text.write(
                        "⏸️ Processamento pausado."
                    )

                    st.warning(
                        "⚠️ "
                        + error_info["titulo"]
                    )

                    st.info(
                        "Os blocos já analisados foram preservados "
                        "no cache. Quando a cota gratuita estiver "
                        "disponível novamente, envie o mesmo documento "
                        "e clique em **Processar documentos**. "
                        "O sistema reutilizará o trabalho já concluído."
                    )

                    detail_text.write(
                        "💾 Progresso parcial preservado."
                    )

                # ------------------------------------------------
                # Falha de OCR
                # ------------------------------------------------

                elif error_info["tipo"] == "ocr":

                    progress_text.write(
                        "❌ Falha na extração de texto."
                    )

                    detail_text.empty()

                    st.error(
                        "🔎 " + error_info["titulo"]
                    )

                    st.info(
                        error_info["mensagem"]
                    )

                # ------------------------------------------------
                # Documento sem texto suficiente
                # ------------------------------------------------

                elif error_info["tipo"] == "sem_texto":

                    progress_text.write(
                        "⚠️ Documento sem texto suficiente."
                    )

                    detail_text.empty()

                    st.warning(
                        error_info["titulo"]
                    )

                    st.info(
                        error_info["mensagem"]
                    )

                # ------------------------------------------------
                # Configuração
                # ------------------------------------------------

                elif error_info["tipo"] == "configuracao":

                    progress_text.write(
                        "❌ Configuração incompleta."
                    )

                    detail_text.empty()

                    st.error(
                        error_info["titulo"]
                    )

                    st.info(
                        error_info["mensagem"]
                    )

                # ------------------------------------------------
                # Arquivo inválido
                # ------------------------------------------------

                elif error_info["tipo"] == "arquivo":

                    progress_text.write(
                        "❌ Arquivo não suportado."
                    )

                    detail_text.empty()

                    st.error(
                        error_info["titulo"]
                    )

                    st.info(
                        error_info["mensagem"]
                    )

                # ------------------------------------------------
                # Erro inesperado
                # ------------------------------------------------

                else:

                    progress_text.write(
                        "❌ O processamento foi interrompido."
                    )

                    detail_text.empty()

                    st.error(
                        error_info["titulo"]
                    )

                    st.info(
                        error_info["mensagem"]
                    )




# ============================================================
# ABA 2 — CONSULTA
# ============================================================

with tab2:

    st.subheader(
        "2. Base estruturada"
    )

    policies = list_policies()

    if not policies:

        st.info(
            "Nenhuma apólice processada."
        )

    else:

        # ----------------------------------------------------
        # Lista da base
        # ----------------------------------------------------

        st.markdown(
            "### 🗃️ Apólices armazenadas"
        )

        st.dataframe(
            pd.DataFrame(policies),
            width="stretch",
            hide_index=True
        )

        st.divider()

        # ----------------------------------------------------
        # Seleção
        # ----------------------------------------------------

        options = {
            f"{p['id']} — {p['filename']}":
                p["id"]
            for p in policies
        }

        choice = st.selectbox(
            "Abrir apólice",
            list(options)
        )

        p = get_policy(
            options[choice]
        )

        # ----------------------------------------------------
        # Validação do registro
        # ----------------------------------------------------

        if not p:

            st.error(
                "Não foi possível localizar esta apólice na base."
            )

            st.info(
                "O registro pode ter sido removido ou alterado. "
                "Atualize a página para recarregar a base."
            )

        elif not isinstance(
            p.get("structured"),
            dict
        ):

            st.error(
                "Os dados estruturados desta apólice "
                "não puderam ser carregados."
            )

            st.info(
                "O registro permanece na base, mas os dados "
                "estruturados estão inválidos ou corrompidos."
            )

        else:

            # ------------------------------------------------
            # Exibição estruturada
            # ------------------------------------------------

            show_policy_analysis(
                p["structured"]
            )

            # ------------------------------------------------
            # Texto original
            # ------------------------------------------------

            with st.expander(
                "📄 Texto extraído / OCR"
            ):

                raw_text = (
                    p.get("raw_text")
                    or "Texto extraído não disponível."
                )

                st.text(
                    raw_text[:30000]
                )


# ============================================================
# ABA 3 — COMPARAÇÃO
# ============================================================

with tab3:

    st.subheader(
        "3. Comparação inteligente"
    )

    st.write(
        "Selecione duas apólices para comparar "
        "limites, franquias, vigência, coberturas, "
        "exclusões, extensões e condições."
    )

    policies = list_policies()

    if len(policies) < 2:

        st.warning(
            "Processe pelo menos duas apólices "
            "para utilizar a comparação."
        )

    else:

        opts = {
            f"{p['id']} — {p['filename']}":
                p["id"]
            for p in policies
        }

        labels = list(opts)

        c1, c2 = st.columns(2)

        with c1:

            a_label = st.selectbox(
                "Apólice A",
                labels,
                key="a"
            )

        with c2:

            b_label = st.selectbox(
                "Apólice B",
                labels,
                index=(
                    1
                    if len(labels) > 1
                    else 0
                ),
                key="b"
            )

        # ----------------------------------------------------
        # Informações básicas antes da comparação
        # ----------------------------------------------------

        a_preview = get_policy(
            opts[a_label]
        )

        b_preview = get_policy(
            opts[b_label]
        )

        # Proteção contra registros ausentes ou corrompidos.
        comparison_records_valid = True

        if a_preview is None or b_preview is None:
            st.error(
                "Não foi possível carregar uma das apólices selecionadas. "
                "O registro pode ter sido removido ou estar indisponível."
            )
            comparison_records_valid = False

        elif (
            not isinstance(a_preview.get("structured"), dict)
            or not isinstance(b_preview.get("structured"), dict)
            or not a_preview.get("structured")
            or not b_preview.get("structured")
        ):
            st.error(
                "Uma das apólices selecionadas possui dados estruturados "
                "ausentes ou inválidos e não pode ser comparada."
            )
            comparison_records_valid = False

    if comparison_records_valid:

        ca, cb = st.columns(2)

        with ca:

            st.markdown(
                "#### 🅰️ Apólice A"
            )

            st.write(
                f"**Arquivo:** "
                f"{a_preview['filename']}"
            )

            st.write(
                "**Seguradora:** "
                f"{a_preview['structured'].get('seguradora') or 'Não identificado'}"
            )

            st.write(
                "**Limite:** "
                f"{a_preview['structured'].get('limite_responsabilidade') or 'Não identificado'}"
            )

        with cb:

            st.markdown(
                "#### 🅱️ Apólice B"
            )

            st.write(
                f"**Arquivo:** "
                f"{b_preview['filename']}"
            )

            st.write(
                "**Seguradora:** "
                f"{b_preview['structured'].get('seguradora') or 'Não identificado'}"
            )

            st.write(
                "**Limite:** "
                f"{b_preview['structured'].get('limite_responsabilidade') or 'Não identificado'}"
            )

        st.divider()

        # ----------------------------------------------------
        # Botão comparar
        # ----------------------------------------------------

        if st.button(
            "Comparar apólices",
            type="primary"
        ):

            if (
                opts[a_label]
                == opts[b_label]
            ):

                st.error(
                    "Selecione duas "
                    "apólices diferentes."
                )

            else:

                a = a_preview
                b = b_preview

                try:

                    with st.spinner(
                        "Comparando cláusulas "
                        "e condições..."
                    ):

                        comp = (
                            ComparisonAgent()
                            .compare(
                                a["structured"],
                                b["structured"]
                            )
                        )

                    show_comparison_result(comp,a,b)

                 
                    # ----------------------------------------
                    # Relatório
                    # ----------------------------------------

                    report = (
                        ReportAgent()
                        .markdown(
                            comp,
                            a["filename"],
                            b["filename"]
                        )
                    )

                    st.divider()

                    st.download_button(
                        "📥 Baixar relatório comparativo (.md)",
                        report,
                        file_name=(
                            "relatorio_comparativo_D&O.md"
                        ),
                        mime="text/markdown"
                    )

                except Exception as e:

                    error_message = str(e)
                    error_lower = error_message.lower()

                    if (
                        "free-models-per-day"
                        in error_lower

                        or (
                            "429"
                            in error_message

                            and "rate limit"
                            in error_lower
                        )
                    ):

                        st.warning(
                            "O limite diário gratuito "
                            "da IA foi atingido. "
                            "A comparação poderá ser "
                            "executada quando a cota "
                            "estiver disponível novamente."
                        )

                    else:

                        st.error(
                            "Não foi possível realizar "
                            f"a comparação: {error_message}"
                        )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "MVP acadêmico. A extração por IA pode conter erros; "
    "sempre confira a evidência no documento original."
)