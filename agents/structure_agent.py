import re


EXPECTED_LISTS = [
    "coberturas",
    "exclusoes",
    "extensoes",
    "definicoes_relevantes",
    "clausulas_relevantes",
    "observacoes",
    "evidencias",
]

EXPECTED_SCALARS = [
    "seguradora",
    "segurado",
    "numero_apolice",
    "vigencia_inicio",
    "vigencia_fim",
    "moeda",
    "limite_responsabilidade",
    "limite_agregado",
    "franquia",
    "premio",
]


class StructureAgent:

    def normalize(self, data):
        if not isinstance(data, dict):
            data = {}

        out = {}

        # -------------------------------------------------
        # Campos escalares
        # -------------------------------------------------

        for key in EXPECTED_SCALARS:
            value = data.get(key)

            if isinstance(value, str):
                value = value.strip()

                if not value:
                    value = None

            out[key] = value

        # -------------------------------------------------
        # Campos de lista
        # -------------------------------------------------

        for key in EXPECTED_LISTS:
            value = data.get(key, [])

            if value is None:
                value = []

            elif not isinstance(value, list):
                value = [value]

            out[key] = value

        # -------------------------------------------------
        # Proteção final:
        # Processo SUSEP NÃO é número da apólice
        # -------------------------------------------------

        numero_apolice = out.get("numero_apolice")

        if self._looks_like_susep_process(numero_apolice):

            out["numero_apolice"] = None

            self._add_observation(
                out,
                (
                    "Uma referência com formato de Processo SUSEP "
                    "foi descartada do campo número da apólice, "
                    "pois Processo SUSEP não comprova o número "
                    "individual da apólice."
                ),
            )

        # -------------------------------------------------
        # Classificação determinística do documento
        # -------------------------------------------------

        out["tipo_documento"] = (
            self._classify_document(data, out)
        )

        # -------------------------------------------------
        # Identificação do ramo do seguro
        # -------------------------------------------------

        out["ramo_seguro"] = self._classify_insurance_line(
            data,
            out
        )

        out["observacoes"] = self._clean_observations(
            out.get("observacoes", [])
        )

        return out

    # =====================================================
    # RAMO DO SEGURO
    # =====================================================

    def _classify_insurance_line(self, original, normalized):
        searchable_text = self._collect_searchable_text(original)
        text = searchable_text.lower()

        # -------------------------------------------------
        # Evidências fortes de D&O
        # -------------------------------------------------

        dao_terms = [
            "directors and officers",
            "directors & officers",
            "d&o",
            "responsabilidade civil de administradores",
            "responsabilidade civil administradores",
            "responsabilidade civil de diretores",
            "seguro de responsabilidade civil de administradores",
        ]

        if any(term in text for term in dao_terms):
            return "D&O — Responsabilidade Civil de Administradores"

        # -------------------------------------------------
        # Outros ramos identificáveis
        # -------------------------------------------------

        travel_terms = [
            "seguro de viagem",
            "seguro viagem",
            "travel insurance",
            "international travel insurance",
            "medical expenses overseas",
            "medical repatriation",
            "repatriation of remains",
        ]

        if any(term in text for term in travel_terms):
            return "Seguro Viagem"

        # -------------------------------------------------
        # Não assumir que todo documento de seguro é D&O
        # -------------------------------------------------

        return "Não identificado"

    # =====================================================
    # TIPO DE DOCUMENTO
    # =====================================================

    def _classify_document(self, original, normalized):
        searchable_text = self._collect_searchable_text(original)
        text = searchable_text.lower()

        # Dados individualizados têm prioridade sobre simples menções
        # a Condições Gerais dentro do documento.
        if self._has_individualized_policy_data(normalized):
            if (
                "especificação da apólice" in text
                or "especificacao da apolice" in text
                or "especificações da apólice" in text
                or "especificacoes da apolice" in text
                or "policy schedule" in text
            ):
                return "Especificação / Apólice"

            return "Apólice / Documento individualizado"

        if "endosso" in text or "endorsement" in text:
            return "Endosso"

        if (
            "condições gerais" in text
            or "condicoes gerais" in text
            or "general conditions" in text
        ):
            return "Condições Gerais"

        return "Não identificado"



    # =====================================================
    # DADOS INDIVIDUALIZADOS
    # =====================================================

    @staticmethod
    def _has_individualized_policy_data(data):

        indicators = [
            data.get("numero_apolice"),
            data.get("segurado"),
            data.get("vigencia_inicio"),
            data.get("vigencia_fim"),
            data.get("premio"),
            data.get("limite_responsabilidade"),
            data.get("franquia"),
        ]

        identified = sum(
            1
            for value in indicators
            if value not in (
                None,
                "",
                [],
                {},
            )
        )

        # Exigimos pelo menos dois sinais para evitar que
        # uma informação genérica isolada transforme
        # Condições Gerais em uma apólice individualizada.
        return identified >= 2

    # =====================================================
    # TEXTO UTILIZADO NA CLASSIFICAÇÃO
    # =====================================================

    def _collect_searchable_text(self, data):

        pieces = []

        def collect(value):

            if value is None:
                return

            if isinstance(value, str):
                pieces.append(value)
                return

            if isinstance(value, dict):
                for item in value.values():
                    collect(item)
                return

            if isinstance(value, list):
                for item in value:
                    collect(item)

        collect(data)

        return " ".join(pieces)

    # =====================================================
    # PROCESSO SUSEP
    # =====================================================

    @staticmethod
    def _looks_like_susep_process(value):

        if value is None:
            return False

        text = str(value).strip().lower()

        if not text:
            return False

        if "susep" in text:
            return True

        # Exemplo:
        # 15414.901016/2017-01
        return bool(
            re.fullmatch(
                r"\d{5}\.\d{6}/\d{4}-\d{2}",
                text,
            )
        )

    # =====================================================
    # OBSERVAÇÕES
    # =====================================================

    @staticmethod
    def _add_observation(data, message):

        observations = data.setdefault(
            "observacoes",
            [],
        )

        if message not in observations:
            observations.append(message)

    # =====================================================

    @staticmethod
    def _clean_observations(observations):

        if not observations:
            return []

        cleaned = []

        # Categorias que já apareceram.
        # Evita várias observações dizendo essencialmente
        # a mesma coisa.
        seen_categories = set()

        for observation in observations:

            # -------------------------------------------------
            # Normalização para texto
            # -------------------------------------------------

            if isinstance(observation, dict):
                text = (
                    observation.get("descricao")
                    or observation.get("texto")
                    or observation.get("valor")
                    or observation.get("nome")
                )

                if not text:
                    continue

                text = str(text).strip()

            else:
                text = str(observation).strip()

            if not text:
                continue

            normalized = re.sub(
                r"\s+",
                " ",
                text.lower(),
            )

            # -------------------------------------------------
            # 1. Mensagens técnicas internas
            # -------------------------------------------------

            if normalized.startswith(
                "conflito entre blocos"
            ):
                continue

            # -------------------------------------------------
            # 2. Processo SUSEP não é número da apólice
            # -------------------------------------------------

            if (
                "susep" in normalized
                and (
                    "número da apólice" in normalized
                    or "numero da apolice" in normalized
                )
                and (
                    "não é" in normalized
                    or "não corresponde" in normalized
                    or "não deve ser confundido" in normalized
                    or "descartad" in normalized
                    or "processo administrativo" in normalized
                )
            ):
                category = "susep_nao_apolice"

            # -------------------------------------------------
            # 3. Ausência de dados individualizados
            # -------------------------------------------------

            elif (
                (
                    "não há identificação" in normalized
                    or "não foram identificad" in normalized
                    or "não contendo valores" in normalized
                )
                and any(
                    term in normalized
                    for term in [
                        "segurado",
                        "vigência",
                        "vigencia",
                        "limite",
                        "franquia",
                        "prêmio",
                        "premio",
                        "número de apólice",
                        "numero de apolice",
                    ]
                )
            ):
                category = "dados_individualizados_ausentes"

            # -------------------------------------------------
            # 3. Dados individualizados ausentes /
            #    dependentes da Especificação
            # -------------------------------------------------

            elif (
                "especificação" in normalized
                or "especificacao" in normalized
            ) and any(
                term in normalized
                for term in [
                    "limite",
                    "franquia",
                    "prêmio",
                    "premio",
                    "vigência",
                    "vigencia",
                    "número de apólice",
                    "numero de apolice",
                    "segurado",
                ]
            ):
                category = "dados_especificacao"

            # -------------------------------------------------
            # 4. Coberturas condicionais à contratação
            # -------------------------------------------------

            elif (
                "contratad" in normalized
                or "contratação" in normalized
                or "contratacao" in normalized
            ) and (
                "cobertura" in normalized
                or "extens" in normalized
            ):
                category = "coberturas_condicionais"

            # -------------------------------------------------
            # 5. Identificação das Condições Gerais
            # -------------------------------------------------

            elif (
                "condições gerais" in normalized
                or "condicoes gerais" in normalized
            ) and (
                "documento" in normalized
                or "versão" in normalized
                or "versao" in normalized
            ):
                category = "identificacao_documento"

            # -------------------------------------------------
            # 6. Demais observações permanecem individuais
            # -------------------------------------------------


            elif (
                "versão vigente" in normalized
                or "versao vigente" in normalized
            ):
                category = "versao_documento"

            else:
                category = None

            # Se uma observação equivalente já foi mantida,
            # descartamos as seguintes.
            if category:

                if category in seen_categories:
                    continue

                seen_categories.add(category)

            # -------------------------------------------------
            # Duplicata textual
            # -------------------------------------------------

            duplicate = False

            for existing in cleaned:

                existing_normalized = re.sub(
                    r"\s+",
                    " ",
                    existing.lower(),
                )

                if existing_normalized == normalized:
                    duplicate = True
                    break

            if duplicate:
                continue

            cleaned.append(text)

        return cleaned
    