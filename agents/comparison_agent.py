import os
import json
import re
import unicodedata
from datetime import datetime

from openai import OpenAI


class ComparisonAgent:

    def __init__(self):

        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY não encontrada no .env"
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=120.0
        )

        self.model = os.getenv(
            "OPENROUTER_MODEL",
            "openrouter/free"
        )

        # Impede seleção acidental de modelo pago
        if self.model != "openrouter/free":
            raise ValueError(
                "Modelo bloqueado. Use somente openrouter/free."
            )

    # ======================================================
    # COMPARAÇÃO PRINCIPAL
    # ======================================================

    def compare(self, a, b):

        # --------------------------------------------------
        # 1. Comparação objetiva local
        # --------------------------------------------------

        local_differences = self._compare_objective_fields(
            a,
            b
        )

        # --------------------------------------------------
        # 2. Tenta comparação semântica por IA
        # --------------------------------------------------

        try:

            semantic_result = self._compare_semantic_fields(
                a,
                b,
                local_differences
            )

            semantic_differences = (
                semantic_result.get(
                    "diferencas",
                    []
                )
                or []
            )

            all_differences = (
                local_differences
                + semantic_differences
            )

            return {
                "resumo_executivo":
                    semantic_result.get(
                        "resumo_executivo",
                        ""
                    ),

                "diferencas":
                    all_differences,

                "pontos_atencao":
                    semantic_result.get(
                        "pontos_atencao",
                        []
                    )
                    or [],

                "similaridades_relevantes":
                    semantic_result.get(
                        "similaridades_relevantes",
                        []
                    )
                    or [],

                "analise_ia_disponivel":
                    True,

                "modo_comparacao":
                    "hibrido"
            }

        # --------------------------------------------------
        # 3. Se a IA falhar
        # --------------------------------------------------

        except Exception as e:

            error_message = str(e)
            error_lower = error_message.lower()

            rate_limit = (
                "free-models-per-day"
                in error_lower

                or (
                    "429" in error_message
                    and "rate limit" in error_lower
                )

                or (
                    "cota diária gratuita"
                    in error_lower
                )
            )

            # Se acabou a cota, mantém a comparação local
            if rate_limit:

                return {
                    "resumo_executivo":
                        (
                            "A comparação objetiva foi realizada "
                            "localmente. A análise semântica de "
                            "coberturas, exclusões, extensões e "
                            "cláusulas não pôde ser executada "
                            "porque a cota gratuita da IA está "
                            "temporariamente indisponível."
                        ),

                    "diferencas":
                        local_differences,

                    "pontos_atencao": [
                        (
                            "A análise contratual por IA está "
                            "temporariamente indisponível. "
                            "As diferenças exibidas correspondem "
                            "aos campos objetivos comparados "
                            "localmente."
                        )
                    ],

                    "similaridades_relevantes":
                        [],

                    "analise_ia_disponivel":
                        False,

                    "modo_comparacao":
                        "local"
                }

            # Outros erros continuam sendo mostrados
            raise

    # ======================================================
    # COMPARAÇÃO OBJETIVA LOCAL
    # ======================================================

    def _compare_objective_fields(self, a, b):

        differences = []

        fields = [
            (
                "Limite de responsabilidade",
                "limite_responsabilidade",
                "alto"
            ),
            (
                "Limite agregado",
                "limite_agregado",
                "alto"
            ),
            (
                "Franquia / Retenção",
                "franquia",
                "alto"
            ),
            (
                "Prêmio",
                "premio",
                "medio"
            ),
            (
                "Moeda",
                "moeda",
                "alto"
            ),
            (
                "Início da vigência",
                "vigencia_inicio",
                "medio"
            ),
            (
                "Fim da vigência",
                "vigencia_fim",
                "medio"
            ),
            (
                "Seguradora",
                "seguradora",
                "baixo"
            ),
            (
                "Segurado",
                "segurado",
                "alto"
            )
        ]

        for category, field, relevance in fields:

            value_a = a.get(field)
            value_b = b.get(field)

            # Se os dois estão vazios, não há o que comparar
            if (
                self._is_empty(value_a)
                and self._is_empty(value_b)
            ):
                continue

            # --------------------------------------------------
            # Moeda
            # --------------------------------------------------

            if field == "moeda":

                normalized_a = self._normalize_currency(
                    value_a
                )

                normalized_b = self._normalize_currency(
                    value_b
                )

            # --------------------------------------------------
            # Campos monetários
            # --------------------------------------------------

            elif field in [
                "limite_responsabilidade",
                "limite_agregado",
                "premio"
            ]:

                normalized_a = self._extract_monetary_value(
                    value_a
                )

                normalized_b = self._extract_monetary_value(
                    value_b
                )

                # Se não conseguir interpretar o número,
                # volta para comparação textual
                if normalized_a is None:
                    normalized_a = self._normalize_value(
                        value_a
                    )

                if normalized_b is None:
                    normalized_b = self._normalize_value(
                        value_b
                    )

            # --------------------------------------------------
            # Franquia / retenção
            # --------------------------------------------------

            elif field == "franquia":

                value_number_a = (
                    self._extract_monetary_value(
                        value_a
                    )
                )

                value_number_b = (
                    self._extract_monetary_value(
                        value_b
                    )
                )

                # Caso consiga identificar os dois valores
                if (
                    value_number_a is not None
                    and value_number_b is not None
                ):

                    normalized_a = value_number_a
                    normalized_b = value_number_b

                else:

                    normalized_a = self._normalize_value(
                        value_a
                    )

                    normalized_b = self._normalize_value(
                        value_b
                    )

            # --------------------------------------------------
            # Datas
            # --------------------------------------------------

            elif field in [
                "vigencia_inicio",
                "vigencia_fim"
            ]:

                normalized_a = self._normalize_date(
                    value_a
                )

                normalized_b = self._normalize_date(
                    value_b
                )

            # --------------------------------------------------
            # Demais campos
            # --------------------------------------------------

            else:

                normalized_a = self._normalize_value(
                    value_a
                )

                normalized_b = self._normalize_value(
                    value_b
                )

            # --------------------------------------------------
            # Registra diferença real
            # --------------------------------------------------

            if normalized_a != normalized_b:

                differences.append({
                    "categoria":
                        category,

                    "apolice_a":
                        self._display_value(
                            value_a
                        ),

                    "apolice_b":
                        self._display_value(
                            value_b
                        ),

                    "impacto":
                        relevance,

                    "comentario":
                        self._objective_comment(
                            category,
                            value_a,
                            value_b
                        ),

                    "origem":
                        "comparacao_local"
                })

        # ------------------------------------------------------
        # Compara condição/base da franquia separadamente
        # ------------------------------------------------------

        franchise_a = a.get("franquia")
        franchise_b = b.get("franquia")

        franchise_value_a = (
            self._extract_monetary_value(
                franchise_a
            )
        )

        franchise_value_b = (
            self._extract_monetary_value(
                franchise_b
            )
        )

        condition_a = self._extract_condition(
            franchise_a
        )

        condition_b = self._extract_condition(
            franchise_b
        )

        # Só cria alerta sobre condição quando os valores
        # monetários são iguais.
        if (
            franchise_value_a is not None
            and franchise_value_b is not None
            and franchise_value_a == franchise_value_b
        ):

            # Se os dois têm condições explícitas e diferentes
            if (
                condition_a
                and condition_b
                and condition_a != condition_b
            ):

                differences.append({
                    "categoria":
                        "Base de aplicação da franquia",

                    "apolice_a":
                        condition_a,

                    "apolice_b":
                        condition_b,

                    "impacto":
                        "alto",

                    "comentario":
                        (
                            "Os valores monetários das franquias "
                            "são iguais, mas a base de aplicação "
                            "explicitamente identificada é diferente."
                        ),

                    "origem":
                        "comparacao_local"
                })

            # A tem condição explícita e B não
            elif condition_a and not condition_b:

                differences.append({
                    "categoria":
                        "Base de aplicação da franquia",

                    "apolice_a":
                        condition_a,

                    "apolice_b":
                        "Não identificada no campo extraído",

                    "impacto":
                        "medio",

                    "comentario":
                        (
                            "O valor monetário da franquia é igual "
                            "nas duas apólices. Entretanto, a Apólice A "
                            "informa explicitamente a base de aplicação, "
                            "enquanto essa condição não foi identificada "
                            "no campo extraído da Apólice B. Isso não "
                            "significa necessariamente que a condição "
                            "não exista no documento."
                        ),

                    "origem":
                        "comparacao_local"
                })

            # B tem condição explícita e A não
            elif condition_b and not condition_a:

                differences.append({
                    "categoria":
                        "Base de aplicação da franquia",

                    "apolice_a":
                        "Não identificada no campo extraído",

                    "apolice_b":
                        condition_b,

                    "impacto":
                        "medio",

                    "comentario":
                        (
                            "O valor monetário da franquia é igual "
                            "nas duas apólices. Entretanto, a Apólice B "
                            "informa explicitamente a base de aplicação, "
                            "enquanto essa condição não foi identificada "
                            "no campo extraído da Apólice A. Isso não "
                            "significa necessariamente que a condição "
                            "não exista no documento."
                        ),

                    "origem":
                        "comparacao_local"
                })

        return differences

    # ======================================================
    # COMENTÁRIOS OBJETIVOS
    # ======================================================

    def _objective_comment(
        self,
        category,
        value_a,
        value_b
    ):

        if self._is_empty(value_a):

            return (
                "O campo não foi identificado na "
                "Apólice A, enquanto há informação "
                "correspondente na Apólice B."
            )

        if self._is_empty(value_b):

            return (
                "O campo foi identificado na Apólice A, "
                "mas não foi identificado na Apólice B."
            )

        if category == "Limite de responsabilidade":

            return (
                "As apólices apresentam limites de "
                "responsabilidade diferentes."
            )

        if category == "Limite agregado":

            return (
                "Os limites agregados informados "
                "são diferentes."
            )

        if category == "Franquia / Retenção":

            return (
                "As apólices apresentam valores monetários "
                "de franquia ou retenção diferentes."
            )

        if category == "Prêmio":

            return (
                "Os valores de prêmio informados "
                "são diferentes."
            )

        if category == "Moeda":

            return (
                "As apólices utilizam moedas diferentes."
            )

        if category in [
            "Início da vigência",
            "Fim da vigência"
        ]:

            return (
                "Os períodos de vigência informados "
                "não são iguais."
            )

        if category == "Seguradora":

            return (
                "As apólices foram emitidas por "
                "seguradoras diferentes."
            )

        if category == "Segurado":

            return (
                "Os segurados identificados nos "
                "documentos são diferentes."
            )

        return (
            "Os documentos apresentam valores "
            "diferentes para este campo."
        )

    # ======================================================
    # COMPARAÇÃO SEMÂNTICA COM IA
    # ======================================================

    def _compare_semantic_fields(
        self,
        a,
        b,
        local_differences
    ):

        semantic_a = {
            "coberturas":
                a.get("coberturas", []),

            "exclusoes":
                a.get("exclusoes", []),

            "extensoes":
                a.get("extensoes", []),

            "definicoes_relevantes":
                a.get(
                    "definicoes_relevantes",
                    []
                ),

            "clausulas_relevantes":
                a.get(
                    "clausulas_relevantes",
                    []
                ),

            "observacoes":
                a.get(
                    "observacoes",
                    []
                )
        }

        semantic_b = {
            "coberturas":
                b.get("coberturas", []),

            "exclusoes":
                b.get("exclusoes", []),

            "extensoes":
                b.get("extensoes", []),

            "definicoes_relevantes":
                b.get(
                    "definicoes_relevantes",
                    []
                ),

            "clausulas_relevantes":
                b.get(
                    "clausulas_relevantes",
                    []
                ),

            "observacoes":
                b.get(
                    "observacoes",
                    []
                )
        }

        prompt = f"""
Você é um analista técnico especializado em seguros D&O.

Uma comparação determinística dos campos objetivos já
foi realizada pelo sistema local.

NÃO repita diferenças de:
- seguradora
- segurado
- moeda
- limite de responsabilidade
- limite agregado
- valor da franquia ou retenção
- prêmio
- datas de vigência

Sua tarefa é analisar SOMENTE diferenças semânticas e
contratuais entre os documentos.

Compare:
- coberturas
- exclusões
- extensões
- definições relevantes
- cláusulas relevantes
- condições contratuais
- observações documentais relevantes

IMPORTANTE:

1. Compare exclusivamente os dados fornecidos.
2. Não invente informações.
3. Não forneça aconselhamento jurídico.
4. Não suponha que uma cobertura descrita em Condições
   Gerais tenha sido efetivamente contratada.
5. Ausência de informação extraída não significa
   necessariamente ausência da cláusula no documento.
6. Destaque diferenças materiais de redação ou escopo.
7. Evite duplicar diferenças já encontradas pelo sistema
   local.
8. "impacto" representa relevância comparativa documental,
   e não conclusão jurídica.
9. Se duas informações diferirem apenas na forma de
   escrever o mesmo valor, não registre como diferença.
10. Não trate BRL e R$ como moedas diferentes.
11. Se o valor monetário de uma franquia for igual, mas
    apenas um dos documentos informar "por sinistro",
    "por reclamação", "por evento" ou expressão semelhante,
    analise apenas a diferença da condição, sem afirmar
    que os valores das franquias são diferentes.

Retorne SOMENTE JSON válido neste formato:

{{
    "resumo_executivo": "texto",

    "diferencas": [
        {{
            "categoria": "Cobertura, Exclusão, Extensão, Definição ou Cláusula",
            "apolice_a": "texto",
            "apolice_b": "texto",
            "impacto": "baixo|medio|alto",
            "comentario": "explicação objetiva"
        }}
    ],

    "pontos_atencao": [
        "texto"
    ],

    "similaridades_relevantes": [
        "texto"
    ]
}}

DIFERENÇAS OBJETIVAS JÁ IDENTIFICADAS LOCALMENTE:

{json.dumps(
    local_differences,
    ensure_ascii=False,
    indent=2
)}

CONTEÚDO CONTRATUAL DA APÓLICE A:

{json.dumps(
    semantic_a,
    ensure_ascii=False,
    indent=2
)}

CONTEÚDO CONTRATUAL DA APÓLICE B:

{json.dumps(
    semantic_b,
    ensure_ascii=False,
    indent=2
)}
"""

        response = (
            self.client
            .chat.completions
            .create(
                model=self.model,

                messages=[
                    {
                        "role":
                            "system",

                        "content":
                            "Você realiza comparação "
                            "documental factual de "
                            "seguros D&O."
                    },

                    {
                        "role":
                            "user",

                        "content":
                            prompt
                    }
                ],

                temperature=0
            )
        )

        result = (
            response
            .choices[0]
            .message
            .content
        )

        return self._parse_json(
            result
        )

    # ======================================================
    # NORMALIZAÇÃO
    # ======================================================

    @staticmethod
    def _is_empty(value):

        if value is None:
            return True

        if isinstance(value, str):

            cleaned = value.strip().lower()

            return cleaned in [
                "",
                "null",
                "none",
                "não identificado",
                "nao identificado",
                "não informado",
                "nao informado"
            ]

        return False

    # ------------------------------------------------------
    # Remove acentos para comparação textual
    # ------------------------------------------------------

    @staticmethod
    def _remove_accents(value):

        if value is None:
            return None

        text = str(value)

        return "".join(
            char
            for char in unicodedata.normalize(
                "NFD",
                text
            )
            if unicodedata.category(char) != "Mn"
        )

    # ------------------------------------------------------
    # Normalização de moeda
    # ------------------------------------------------------

    @staticmethod
    def _normalize_currency(value):

        if value is None:
            return None

        value = str(value).strip().lower()

        value_without_accents = "".join(
            char
            for char in unicodedata.normalize(
                "NFD",
                value
            )
            if unicodedata.category(char) != "Mn"
        )

        value_without_accents = re.sub(
            r"\s+",
            " ",
            value_without_accents
        ).strip()

        currency_aliases = {
            "brl": "BRL",
            "r$": "BRL",
            "real": "BRL",
            "reais": "BRL",
            "real brasileiro": "BRL",
            "reais brasileiros": "BRL",

            "usd": "USD",
            "us$": "USD",
            "u$": "USD",
            "$": "USD",
            "dolar": "USD",
            "dolares": "USD",
            "dolar americano": "USD",
            "dolares americanos": "USD",

            "eur": "EUR",
            "€": "EUR",
            "euro": "EUR",
            "euros": "EUR",

            "gbp": "GBP",
            "£": "GBP",
            "libra": "GBP",
            "libras": "GBP",
            "libra esterlina": "GBP",
            "libras esterlinas": "GBP"
        }

        return currency_aliases.get(
            value_without_accents,
            value_without_accents.upper()
        )

    # ------------------------------------------------------
    # Extração de valor monetário
    # ------------------------------------------------------
    @staticmethod
    def _extract_monetary_value(value):

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        # Remove espaços extras
        text = re.sub(r"\s+", " ", text)

        # ==================================================
        # PADRÃO BRASILEIRO COM MILHARES
        #
        # Exemplos:
        # R$ 10.000.000,00
        # R$ 50.000,00
        # 1.500.000
        # ==================================================

        match = re.search(
            r"(?<!\d)"
            r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)"
            r"(?![\d.,])",
            text
        )

        if match:

            number = match.group(1)

            # 10.000.000,00
            # vira
            # 10000000.00

            number = number.replace(".", "")
            number = number.replace(",", ".")

            try:
                return round(float(number), 2)
            except ValueError:
                pass

        # ==================================================
        # PADRÃO BRASILEIRO SEM SEPARADOR DE MILHAR
        #
        # Exemplos:
        # 50000,00
        # 10000000,00
        # ==================================================

        match = re.search(
            r"(?<![\d.,])"
            r"(\d+,\d{1,2})"
            r"(?![\d.,])",
            text
        )

        if match:

            number = match.group(1)

            number = number.replace(",", ".")

            try:
                return round(float(number), 2)
            except ValueError:
                pass

        # ==================================================
        # PADRÃO INTERNACIONAL
        #
        # Exemplos:
        # 10,000,000.00
        # 50,000.00
        # ==================================================

        match = re.search(
            r"(?<!\d)"
            r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)"
            r"(?![\d.,])",
            text
        )

        if match:

            number = match.group(1)

            number = number.replace(",", "")

            try:
                return round(float(number), 2)
            except ValueError:
                pass

        # ==================================================
        # NÚMERO DECIMAL SIMPLES
        #
        # Exemplo:
        # 50000.00
        # ==================================================

        match = re.search(
            r"(?<![\d.,])"
            r"(\d+\.\d{1,2})"
            r"(?![\d.,])",
            text
        )

        if match:

            try:
                return round(
                    float(match.group(1)),
                    2
                )
            except ValueError:
                pass

        # ==================================================
        # NÚMERO INTEIRO
        #
        # Exemplo:
        # 10000000
        # ==================================================

        match = re.search(
            r"(?<!\d)"
            r"(\d+)"
            r"(?!\d)",
            text
        )

        if match:

            try:
                return round(
                    float(match.group(1)),
                    2
                )
            except ValueError:
                pass

        return None
    
    # ------------------------------------------------------
    # Condição/base de aplicação da franquia
    # ------------------------------------------------------

    @classmethod
    def _extract_condition(cls, value):

        if value is None:
            return None

        text = cls._remove_accents(
            str(value).lower()
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        conditions = {
            "por sinistro":
                "Por sinistro",

            "por reclamacao":
                "Por reclamação",

            "por evento":
                "Por evento",

            "por ocorrencia":
                "Por ocorrência",

            "por segurado":
                "Por segurado",

            "por administrador":
                "Por administrador",

            "por diretor":
                "Por diretor",

            "por perda":
                "Por perda"
        }

        for expression, label in conditions.items():

            if expression in text:
                return label

        return None

    # ------------------------------------------------------
    # Normalização de datas
    # ------------------------------------------------------

    @staticmethod
    def _normalize_date(value):

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
            "%d-%m-%y"
        ]

        for date_format in formats:

            try:

                parsed = datetime.strptime(
                    text,
                    date_format
                )

                return parsed.strftime(
                    "%Y-%m-%d"
                )

            except ValueError:
                continue

        # Se não reconhecer a data,
        # usa texto normalizado
        return re.sub(
            r"\s+",
            " ",
            text.lower()
        )

    # ------------------------------------------------------
    # Normalização textual geral
    # ------------------------------------------------------

    @classmethod
    def _normalize_value(cls, value):

        if value is None:
            return None

        if isinstance(value, str):

            value = value.strip().lower()

            value = cls._remove_accents(
                value
            )

            # Remove espaços repetidos
            value = re.sub(
                r"\s+",
                " ",
                value
            )

            # Remove espaços nas extremidades
            value = value.strip()

            return value

        return value

    # ------------------------------------------------------
    # Valor exibido ao usuário
    # ------------------------------------------------------

    @staticmethod
    def _display_value(value):

        if value is None:
            return "Não identificado"

        if isinstance(value, str):

            if not value.strip():
                return "Não identificado"

            return value.strip()

        return str(value)

    # ======================================================
    # JSON
    # ======================================================

    @staticmethod
    def _parse_json(s):

        if not s:

            raise ValueError(
                "O modelo retornou uma resposta vazia."
            )

        s = s.strip()

        # Remove ```json no começo
        s = re.sub(
            r"^```(?:json)?\s*",
            "",
            s,
            flags=re.IGNORECASE
        )

        # Remove ``` no final
        s = re.sub(
            r"\s*```$",
            "",
            s
        )

        try:

            return json.loads(s)

        except json.JSONDecodeError:

            start = s.find("{")
            end = s.rfind("}")

            if (
                start >= 0
                and end > start
            ):

                try:

                    return json.loads(
                        s[start:end + 1]
                    )

                except json.JSONDecodeError:
                    pass

            raise ValueError(
                "O modelo não retornou JSON válido."
            )