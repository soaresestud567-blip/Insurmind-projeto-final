class ReportAgent:

    def markdown(
        self,
        comparison,
        name_a,
        name_b
    ):

        # =====================================================
        # INFORMAÇÕES DO MODO DE COMPARAÇÃO
        # =====================================================

        modo = comparison.get(
            "modo_comparacao",
            "desconhecido"
        )

        ia_disponivel = comparison.get(
            "analise_ia_disponivel",
            False
        )

        if modo == "hibrido" and ia_disponivel:

            status = (
                "Comparação híbrida completa — "
                "campos objetivos comparados localmente "
                "e conteúdo contratual analisado por IA."
            )

        elif modo == "local":

            status = (
                "Comparação local — campos objetivos "
                "comparados localmente. A análise "
                "semântica por IA não foi executada."
            )

        else:

            status = (
                "Modo de comparação não identificado."
            )

        # =====================================================
        # CABEÇALHO
        # =====================================================

        lines = [
            "# Relatório Comparativo de Apólices D&O",
            "",
            f"**Apólice A:** {name_a}  ",
            f"**Apólice B:** {name_b}",
            "",
            "## Status da análise",
            "",
            status,
            "",
            "---",
            "",
            "## Resumo executivo",
            ""
        ]

        # =====================================================
        # RESUMO EXECUTIVO
        # =====================================================

        resumo = comparison.get(
            "resumo_executivo"
        )

        if resumo:

            lines.append(
                str(resumo)
            )

        else:

            lines.append(
                "Nenhum resumo executivo foi produzido."
            )

        # =====================================================
        # DIFERENÇAS
        # =====================================================

        lines += [
            "",
            "---",
            "",
            "## Diferenças identificadas",
            ""
        ]

        differences = (
            comparison.get(
                "diferencas",
                []
            )
            or []
        )

        # Ordenação por relevância
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

        if differences:

            for number, difference in enumerate(
                differences,
                start=1
            ):

                categoria = (
                    difference.get(
                        "categoria"
                    )
                    or "Item"
                )

                impacto = str(
                    difference.get(
                        "impacto"
                    )
                    or "não classificado"
                )

                impacto_lower = (
                    impacto.lower()
                )

                # ---------------------------------------------
                # Classificação visual
                # ---------------------------------------------

                if impacto_lower in [
                    "alto",
                    "alta"
                ]:

                    indicador = "🔴"
                    nivel = "ALTA"

                elif impacto_lower in [
                    "medio",
                    "médio",
                    "media",
                    "média"
                ]:

                    indicador = "🟠"
                    nivel = "MÉDIA"

                elif impacto_lower in [
                    "baixo",
                    "baixa"
                ]:

                    indicador = "🟢"
                    nivel = "BAIXA"

                else:

                    indicador = "⚪"
                    nivel = impacto.upper()

                valor_a = (
                    difference.get(
                        "apolice_a"
                    )
                    or "Não informado"
                )

                valor_b = (
                    difference.get(
                        "apolice_b"
                    )
                    or "Não informado"
                )

                comentario = (
                    difference.get(
                        "comentario"
                    )
                    or "Sem comentário adicional."
                )

                origem = (
                    difference.get(
                        "origem"
                    )
                )

                lines += [
                    f"### {number}. {indicador} "
                    f"{categoria}",
                    "",
                    f"**Relevância:** {nivel}",
                    "",
                    f"- **Apólice A:** {valor_a}",
                    f"- **Apólice B:** {valor_b}",
                    "",
                    "**Análise comparativa:**",
                    "",
                    str(comentario),
                    ""
                ]

                # ---------------------------------------------
                # Origem da diferença
                # ---------------------------------------------

                if origem == "comparacao_local":

                    lines += [
                        "*Origem: comparação objetiva local.*",
                        ""
                    ]

                elif origem:

                    lines += [
                        "*Origem: análise semântica por IA.*",
                        ""
                    ]

        else:

            lines += [
                "Nenhuma diferença relevante "
                "foi identificada.",
                ""
            ]

        # =====================================================
        # PONTOS DE ATENÇÃO
        # =====================================================

        lines += [
            "---",
            "",
            "## Pontos de atenção",
            ""
        ]

        attention = (
            comparison.get(
                "pontos_atencao",
                []
            )
            or []
        )

        if attention:

            for item in attention:

                lines.append(
                    f"- {self._item_to_text(item)}"
                )

        else:

            lines.append(
                "Nenhum ponto de atenção "
                "foi identificado."
            )

        # =====================================================
        # SIMILARIDADES
        # =====================================================

        lines += [
            "",
            "---",
            "",
            "## Similaridades relevantes",
            ""
        ]

        similarities = (
            comparison.get(
                "similaridades_relevantes",
                []
            )
            or []
        )

        if similarities:

            for item in similarities:

                lines.append(
                    f"- {self._item_to_text(item)}"
                )

        else:

            if not ia_disponivel:

                lines.append(
                    "A identificação de similaridades "
                    "contratuais depende da análise "
                    "semântica por IA, que não foi "
                    "executada nesta comparação."
                )

            else:

                lines.append(
                    "Nenhuma similaridade relevante "
                    "foi destacada."
                )

        # =====================================================
        # LIMITAÇÕES
        # =====================================================

        lines += [
            "",
            "---",
            "",
            "## Limitações da análise",
            "",
            (
                "Este relatório foi produzido automaticamente "
                "como ferramenta de apoio à análise de apólices "
                "D&O. Os resultados devem ser conferidos com "
                "os documentos originais."
            )
        ]

        if not ia_disponivel:

            lines += [
                "",
                (
                    "**Importante:** nesta comparação, a análise "
                    "semântica por inteligência artificial não "
                    "foi executada. Portanto, diferenças e "
                    "similaridades relacionadas a coberturas, "
                    "exclusões, extensões, definições e cláusulas "
                    "podem não estar representadas neste relatório."
                )
            ]

        lines += [
            "",
            (
                "A ausência de determinada informação nos dados "
                "extraídos não significa necessariamente que essa "
                "informação esteja ausente do documento original."
            ),
            "",
            "> Resultado automatizado para apoio à análise. "
            "Validar contra o documento original."
        ]

        return "\n".join(lines)

    # =========================================================
    # CONVERSÃO SEGURA DE ITENS PARA TEXTO
    # =========================================================

    @staticmethod
    def _item_to_text(item):

        if isinstance(
            item,
            dict
        ):

            return str(
                item.get("descricao")
                or item.get("texto")
                or item.get("valor")
                or item.get("nome")
                or item
            )

        return str(item)