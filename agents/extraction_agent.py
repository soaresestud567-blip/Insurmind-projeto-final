import os
import json
import re
import time
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI


SCHEMA_DESCRIPTION = """
Retorne SOMENTE um objeto JSON válido com EXATAMENTE estas chaves:

seguradora
segurado
numero_apolice
vigencia_inicio
vigencia_fim
moeda
limite_responsabilidade
limite_agregado
franquia
premio
coberturas
exclusoes
extensoes
definicoes_relevantes
clausulas_relevantes
observacoes
evidencias

As chaves coberturas, exclusoes, extensoes, definicoes_relevantes e
clausulas_relevantes devem ser listas de objetos contendo, quando disponível:

nome
descricao
pagina
evidencia_textual

evidencias deve ser uma lista de objetos contendo:

campo
valor
pagina
trecho

REGRAS:
- Use null quando uma informação escalar não estiver presente.
- Use [] quando uma lista não tiver itens identificados.
- Não invente informações.
- Não use conhecimento externo para completar campos.
- Não confunda definição contratual com cobertura efetivamente contratada.
- Preserve valores monetários, percentuais, datas, prazos e nomes.
- Preserve a página indicada no texto sempre que possível.
- "Processo SUSEP", "Processo SUSEP nº" ou equivalente NÃO é número da apólice.
- Só preencha numero_apolice quando o texto identificar explicitamente um número
  de apólice/policy number ou equivalente.
- Só preencha segurado quando houver identificação do segurado/empresa
  efetivamente segurada. Uma definição genérica de "Segurado" não basta.
- Só preencha vigencia_inicio e vigencia_fim quando forem datas efetivas de
  vigência da apólice/documento individualizado.
- Quando o documento apresentar um intervalo explícito de vigência, por exemplo
  "Vigência: 01/10/2026 a 01/10/2027", extraia a primeira data em
  vigencia_inicio e a segunda data em vigencia_fim.
- Não deixe vigencia_inicio ou vigencia_fim nulos quando as datas efetivas
  de início e fim da apólice estiverem explicitamente informadas.
- Datas de versão, revisão, emissão de Condições Gerais ou atualização do
  documento NÃO são datas de vigência da apólice.
- Não transforme um LMG, LMI, limite agregado, franquia, POS, prêmio ou outro
  valor descrito genericamente em valor contratado.
- Se o texto disser que o valor consta da Especificação da Apólice e essa
  Especificação não estiver neste bloco, mantenha o campo correspondente null.
- Uma cobertura descrita em Condições Gerais não comprova contratação.
- Expressões como "caso contratada", "se contratada" ou equivalentes devem ser
  preservadas na descrição/evidência e não convertidas em contratação efetiva.
- Seja conciso. Não reproduza cláusulas inteiras quando um trecho curto basta.
- Não repita o mesmo fato em várias listas sem necessidade.
"""


SCALAR_FIELDS = [
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

LIST_FIELDS = [
    "coberturas",
    "exclusoes",
    "extensoes",
    "definicoes_relevantes",
    "clausulas_relevantes",
    "evidencias",
]


class DailyRateLimitError(Exception):
    """Indica que a cota diária gratuita do provedor acabou."""
    pass


class ExtractionAgent:
    CACHE_VERSION = 2

    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY não encontrada no arquivo .env"
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=120.0,
        )

        self.model = os.getenv(
            "OPENROUTER_MODEL",
            "openrouter/free",
        )

        # Proteção contra uso acidental de modelo pago.
        if self.model != "openrouter/free":
            raise ValueError(
                "Modelo bloqueado. Use somente openrouter/free."
            )

        self.chunk_size = 30000

        # Mantemos o comportamento já testado no projeto atual.
        # Se o provedor ficar instável, este valor pode ser reduzido para 2.
        self.max_workers = 3

        self.cache_root = Path("data/extraction_cache")
        self.cache_root.mkdir(parents=True, exist_ok=True)

    # =========================================================
    # EXTRAÇÃO PRINCIPAL
    # =========================================================

    def extract(self, text, progress_callback=None):
        chunks = self._split_text(text)
        total = len(chunks)

        print(
            f"[ExtractionAgent] Documento dividido em {total} bloco(s)."
        )

        document_hash = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()[:24]

        document_cache = self.cache_root / document_hash
        document_cache.mkdir(parents=True, exist_ok=True)

        print(f"[ExtractionAgent] Cache: {document_cache}")

        consolidated = self._load_consolidated_cache(
            document_cache,
            chunks,
        )

        if consolidated is not None:
            print(
                "[ExtractionAgent] Resultado consolidado recuperado do cache."
            )

            if progress_callback:
                progress_callback(
                    total,
                    total,
                    "Resultado final recuperado do cache",
                )

            return consolidated

        if progress_callback:
            progress_callback(
                0,
                total,
                "Verificando blocos já processados",
            )

        partial_results = [None] * total
        missing_chunks = []

        for index, chunk in enumerate(chunks, start=1):
            cached = self._load_chunk_cache(
                document_cache,
                index,
                chunk,
            )

            if cached is not None:
                partial_results[index - 1] = cached
                print(
                    f"[ExtractionAgent] Bloco {index}/{total} "
                    "recuperado do cache."
                )
            else:
                missing_chunks.append((index, chunk))

        cached_count = total - len(missing_chunks)

        if cached_count:
            print(
                f"[ExtractionAgent] {cached_count}/{total} bloco(s) "
                "já estavam salvos."
            )

            if progress_callback:
                progress_callback(
                    cached_count,
                    total,
                    f"{cached_count} bloco(s) recuperados do cache",
                )

        # Se todos os blocos já existem, a consolidação agora é LOCAL.
        if not missing_chunks:
            result = self._merge_partial_results(partial_results)

            self._save_consolidated_cache(
                document_cache,
                chunks,
                result,
            )

            if progress_callback:
                progress_callback(
                    total,
                    total,
                    "Consolidação local concluída",
                )

            print(
                "[ExtractionAgent] Consolidação local concluída "
                "sem nova chamada de IA."
            )
            return result

        completed = cached_count
        executor = ThreadPoolExecutor(
            max_workers=self.max_workers
        )
        futures = {}

        try:
            for index, chunk in missing_chunks:
                future = executor.submit(
                    self._extract_chunk_with_retry,
                    chunk,
                    index,
                    total,
                )
                futures[future] = (index, chunk)

            for future in as_completed(futures):
                index, chunk = futures[future]

                try:
                    result = future.result()

                except DailyRateLimitError:
                    print(
                        "[ExtractionAgent] Cota diária gratuita atingida."
                    )
                    print(
                        "[ExtractionAgent] Os blocos concluídos foram "
                        "preservados no cache."
                    )

                    for pending in futures:
                        if not pending.done():
                            pending.cancel()
                    raise

                except Exception as e:
                    for pending in futures:
                        if not pending.done():
                            pending.cancel()

                    raise RuntimeError(
                        f"Falha definitiva ao analisar o bloco "
                        f"{index}/{total}: {e}"
                    ) from e

                partial_results[index - 1] = result

                self._save_chunk_cache(
                    document_cache,
                    index,
                    chunk,
                    result,
                )

                completed += 1

                print(
                    f"[ExtractionAgent] Bloco {index}/{total} concluído "
                    f"e salvo no cache. Progresso: {completed}/{total}"
                )

                if progress_callback:
                    progress_callback(
                        completed,
                        total,
                        f"Bloco {index} concluído",
                    )

        finally:
            executor.shutdown(
                wait=True,
                cancel_futures=True,
            )

        # A antiga chamada de IA para consolidação foi removida.
        if progress_callback:
            progress_callback(
                total,
                total,
                "Consolidando resultados localmente",
            )

        result = self._merge_partial_results(partial_results)

        self._save_consolidated_cache(
            document_cache,
            chunks,
            result,
        )

        print(
            "[ExtractionAgent] Resultado consolidado localmente "
            "e salvo no cache."
        )

        if progress_callback:
            progress_callback(
                total,
                total,
                "Concluído",
            )

        return result

    # =========================================================
    # RETRY DOS BLOCOS
    # =========================================================

    def _extract_chunk_with_retry(
        self,
        chunk,
        chunk_number,
        total_chunks,
        max_attempts=3,
    ):
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                print(
                    f"[ExtractionAgent] Bloco {chunk_number}/{total_chunks} "
                    f"- tentativa {attempt}/{max_attempts}"
                )

                return self._extract_chunk(
                    chunk,
                    chunk_number,
                    total_chunks,
                    attempt=attempt,
                )

            except Exception as e:
                if self._is_daily_rate_limit(e):
                    raise DailyRateLimitError(
                        "A cota diária gratuita do OpenRouter foi atingida. "
                        "Os blocos já concluídos foram salvos e poderão ser "
                        "reutilizados na próxima execução."
                    ) from e

                last_error = e
                error_type = type(e).__name__

                print(
                    f"[ExtractionAgent] Erro no bloco {chunk_number} "
                    f"({error_type}): {e}"
                )

                if attempt < max_attempts:
                    wait_time = attempt * 3

                    print(
                        f"[ExtractionAgent] Nova tentativa em "
                        f"{wait_time}s..."
                    )

                    time.sleep(wait_time)

        raise RuntimeError(
            f"Bloco {chunk_number} falhou após {max_attempts} tentativas: "
            f"{last_error}"
        )


    # =========================================================
    # DETECÇÃO DO ERRO 429
    # =========================================================

    @staticmethod
    def _is_daily_rate_limit(error):
        message = str(error).lower()

        return (
            "free-models-per-day" in message
            or (
                "429" in message
                and "rate limit" in message
            )
        )

    # =========================================================
    # CACHE DOS BLOCOS
    # =========================================================

    def _chunk_cache_path(self, cache_dir, index):
        return cache_dir / f"chunk_{index:04d}.json"

    def _save_chunk_cache(
        self,
        cache_dir,
        index,
        chunk,
        result,
    ):
        path = self._chunk_cache_path(
            cache_dir,
            index,
        )

        payload = {
            "cache_version": self.CACHE_VERSION,
            "model": self.model,
            "chunk_hash": hashlib.sha256(
                chunk.encode("utf-8")
            ).hexdigest(),
            "result": result,
        }

        temp_path = path.with_suffix(".tmp")

        with open(
            temp_path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
            )

        temp_path.replace(path)

    def _load_chunk_cache(
        self,
        cache_dir,
        index,
        chunk,
    ):
        path = self._chunk_cache_path(
            cache_dir,
            index,
        )

        if not path.exists():
            return None

        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:
                payload = json.load(f)

            # Caches de blocos da versão anterior ainda podem ser úteis,
            # desde que correspondam exatamente ao mesmo texto.
            expected_hash = hashlib.sha256(
                chunk.encode("utf-8")
            ).hexdigest()

            if payload.get("chunk_hash") != expected_hash:
                return None

            result = payload.get("result")

            if not isinstance(result, dict):
                return None

            # Sanitização local também é aplicada aos caches antigos.
            return self._sanitize_result(result)

        except Exception:
            return None

    # =========================================================
    # CACHE DA CONSOLIDAÇÃO FINAL
    # =========================================================

    def _consolidated_cache_path(self, cache_dir):
        return cache_dir / "consolidated.json"

    @staticmethod
    def _chunks_signature(chunks):
        chunk_hashes = []

        for chunk in chunks:
            chunk_hash = hashlib.sha256(
                chunk.encode("utf-8")
            ).hexdigest()
            chunk_hashes.append(chunk_hash)

        serialized = json.dumps(
            chunk_hashes,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def _save_consolidated_cache(
        self,
        cache_dir,
        chunks,
        result,
    ):
        path = self._consolidated_cache_path(cache_dir)

        payload = {
            "cache_version": self.CACHE_VERSION,
            "model": self.model,
            "chunk_size": self.chunk_size,
            "total_chunks": len(chunks),
            "chunks_signature": self._chunks_signature(chunks),
            "result": result,
        }

        temp_path = path.with_suffix(".tmp")

        with open(
            temp_path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
            )

        temp_path.replace(path)

    def _load_consolidated_cache(
        self,
        cache_dir,
        chunks,
    ):
        path = self._consolidated_cache_path(cache_dir)

        if not path.exists():
            return None

        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:
                payload = json.load(f)

            # A versão 2 invalida o consolidado antigo porque a estratégia
            # mudou de consolidação por IA para consolidação determinística.
            if payload.get("cache_version") != self.CACHE_VERSION:
                print(
                    "[ExtractionAgent] Cache consolidado antigo/incompatível. "
                    "Será reconstruído localmente."
                )
                return None

            if payload.get("model") != self.model:
                return None

            if payload.get("chunk_size") != self.chunk_size:
                return None

            if payload.get("total_chunks") != len(chunks):
                return None

            expected_signature = self._chunks_signature(chunks)

            if payload.get("chunks_signature") != expected_signature:
                return None

            result = payload.get("result")

            if not isinstance(result, dict):
                return None

            return self._sanitize_result(result)

        except Exception as e:
            print(
                "[ExtractionAgent] Não foi possível ler consolidated.json: "
                f"{e}"
            )
            return None

    # =========================================================
    # DIVISÃO DO DOCUMENTO
    # =========================================================

    def _split_text(self, text):
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        current = ""

        # OCRAgent separa páginas com \f.
        pages = text.split("\f")

        if len(pages) == 1:
            pages = text.split("\n\n")

        for page in pages:
            page = page.strip()

            if not page:
                continue

            # Página excepcionalmente grande.
            if len(page) > self.chunk_size:
                if current:
                    chunks.append(current)
                    current = ""

                for start in range(
                    0,
                    len(page),
                    self.chunk_size,
                ):
                    chunks.append(
                        page[start:start + self.chunk_size]
                    )
                continue

            if (
                current
                and len(current) + len(page) + 2 > self.chunk_size
            ):
                chunks.append(current)
                current = page
            else:
                if current:
                    current += "\n\n" + page
                else:
                    current = page

        if current:
            chunks.append(current)

        return chunks or [text]

    # =========================================================
    # EXTRAÇÃO DE UM BLOCO
    # =========================================================

    def _extract_chunk(
        self,
        chunk,
        chunk_number,
        total_chunks,
        attempt=1,
    ):
        # ---------------------------------------------------------
        # Instrução adicional conforme a tentativa.
        #
        # Se o modelo falhar, as próximas respostas ficam
        # progressivamente mais restritivas.
        # ---------------------------------------------------------

        if attempt == 1:
            retry_instruction = """
    Retorne somente o objeto JSON solicitado.
    """

        elif attempt == 2:
            retry_instruction = """
    ATENÇÃO: uma tentativa anterior não produziu JSON válido.

    Nesta tentativa:
    - Retorne SOMENTE JSON válido.
    - Comece a resposta diretamente com {.
    - Termine a resposta diretamente com }.
    - Não use Markdown.
    - Não use ```json.
    - Não escreva explicações antes ou depois do JSON.
    - Seja ainda mais conciso.
    - Reduza evidencia_textual e trecho ao mínimo necessário.
    """

        else:
            retry_instruction = """
    ATENÇÃO MÁXIMA: respostas anteriores não puderam ser interpretadas.

    Sua resposta DEVE ser um único objeto JSON válido.

    REGRAS OBRIGATÓRIAS:
    - O primeiro caractere da resposta deve ser {.
    - O último caractere da resposta deve ser }.
    - Não use Markdown.
    - Não use blocos de código.
    - Não escreva comentários.
    - Não escreva texto fora do JSON.
    - Não transcreva cláusulas.
    - Use descrições curtas.
    - Use evidências extremamente curtas.
    - Se houver dúvida sobre um campo, use null ou [].
    - Priorize JSON válido em vez de detalhamento.
    """

        prompt = f"""
    Você é especialista em análise documental de seguros D&O.

    Este é o BLOCO {chunk_number} de {total_chunks} de um documento maior.

    Extraia SOMENTE informações presentes neste bloco.
    Não tente completar informações usando conhecimento externo.
    Não suponha que uma cobertura descrita nas Condições Gerais tenha sido
    efetivamente contratada.

    IMPORTANTE SOBRE O TAMANHO DA RESPOSTA:
    - Responda de forma objetiva e compacta.
    - Não transcreva páginas ou cláusulas inteiras.
    - Em evidencia_textual/trecho, use apenas o fragmento mínimo necessário.
    - Não repita itens idênticos.
    - A resposta deve conter somente o JSON, sem comentários fora dele.

    {retry_instruction}

    {SCHEMA_DESCRIPTION}

    DOCUMENTO:

    {chunk}
    """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você analisa documentos de seguros D&O com foco "
                        "em extração factual, conservadora e concisa. "
                        "Responda somente JSON válido."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        try:
            result = response.choices[0].message.content
        except Exception as e:
            raise ValueError(
                "A API respondeu, mas não retornou conteúdo utilizável."
            ) from e

        # ---------------------------------------------------------
        # Diagnóstico seguro da resposta.
        #
        # Não imprimimos o conteúdo da apólice.
        # Apenas características estruturais da resposta.
        # ---------------------------------------------------------

        if isinstance(result, str):
            stripped = result.strip()

            print(
                f"[ExtractionAgent] Resposta do bloco {chunk_number}: "
                f"{len(result)} caracteres; "
                f"inicia_com_chave={stripped.startswith('{')}; "
                f"termina_com_chave={stripped.endswith('}')}; "
                f"tentativa={attempt}."
            )
        else:
            print(
                f"[ExtractionAgent] Resposta do bloco {chunk_number}: "
                f"tipo inesperado {type(result).__name__}; "
                f"tentativa={attempt}."
            )

        parsed = self._parse_json(result)

        return self._sanitize_result(parsed)

    # =========================================================
    # CONSOLIDAÇÃO LOCAL / DETERMINÍSTICA
    # =========================================================

    def _merge_partial_results(self, results):
        merged = self._empty_result()
        conflicts = []

        for block_index, raw_result in enumerate(results, start=1):
            if not isinstance(raw_result, dict):
                continue

            result = self._sanitize_result(raw_result)

            # Campos escalares: conserva o primeiro valor factual e registra
            # valores diferentes em observações, sem escolher arbitrariamente.
            for field in SCALAR_FIELDS:
                value = result.get(field)

                if self._is_empty(value):
                    continue

                current = merged.get(field)

                if self._is_empty(current):
                    merged[field] = value
                elif not self._equivalent(current, value):
                    conflict = (
                        f"Conflito entre blocos para '{field}': "
                        f"valor já identificado = {self._short(current)}; "
                        f"bloco {block_index} = {self._short(value)}."
                    )
                    if conflict not in conflicts:
                        conflicts.append(conflict)

            # Listas documentais: união com remoção de duplicidades.
            for field in LIST_FIELDS:
                for item in result.get(field, []):
                    self._append_unique(
                        merged[field],
                        item,
                    )

            # Observações podem ser string ou lista.
            for observation in self._normalize_observations(
                result.get("observacoes")
            ):
                self._append_unique(
                    merged["observacoes"],
                    observation,
                )

        for conflict in conflicts:
            self._append_unique(
                merged["observacoes"],
                conflict,
            )

        # Guarda adicional contra Processo SUSEP usado como nº da apólice.
        policy_number = merged.get("numero_apolice")
        if self._looks_like_susep_process(policy_number):
            self._append_unique(
                merged["observacoes"],
                (
                    "Um valor com aparência de Processo SUSEP foi descartado "
                    "do campo numero_apolice, pois Processo SUSEP não comprova "
                    "o número da apólice."
                ),
            )
            merged["numero_apolice"] = None

        return merged

    @staticmethod
    def _empty_result():
        return {
            "seguradora": None,
            "segurado": None,
            "numero_apolice": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "moeda": None,
            "limite_responsabilidade": None,
            "limite_agregado": None,
            "franquia": None,
            "premio": None,
            "coberturas": [],
            "exclusoes": [],
            "extensoes": [],
            "definicoes_relevantes": [],
            "clausulas_relevantes": [],
            "observacoes": [],
            "evidencias": [],
        }

    def _sanitize_result(self, data):
        if not isinstance(data, dict):
            raise ValueError(
                "O JSON retornado não é um objeto."
            )

        clean = self._empty_result()

        for field in SCALAR_FIELDS:
            value = data.get(field)
            clean[field] = None if self._is_empty(value) else value

        for field in LIST_FIELDS:
            value = data.get(field)

            if isinstance(value, list):
                clean[field] = [
                    item for item in value
                    if not self._is_empty(item)
                ]
            elif self._is_empty(value):
                clean[field] = []
            else:
                # Não perde um item útil só porque o modelo devolveu objeto
                # em vez de lista.
                clean[field] = [value]

        clean["observacoes"] = self._normalize_observations(
            data.get("observacoes")
        )

        # Barreira determinística adicional.
        if self._looks_like_susep_process(
            clean.get("numero_apolice")
        ):
            clean["numero_apolice"] = None
            self._append_unique(
                clean["observacoes"],
                (
                    "Referência com aparência de Processo SUSEP não foi "
                    "considerada número da apólice."
                ),
            )

        return clean

    @staticmethod
    def _normalize_observations(value):
        if value is None:
            return []

        if isinstance(value, list):
            return [
                item for item in value
                if item not in (None, "", [], {})
            ]

        if isinstance(value, str):
            value = value.strip()
            return [value] if value else []

        return [value]

    @staticmethod
    def _is_empty(value):
        if value is None:
            return True

        if isinstance(value, str):
            return not value.strip()

        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0

        return False

    @staticmethod
    def _normalize_for_comparison(value):
        if isinstance(value, (dict, list)):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )

        return re.sub(
            r"\s+",
            " ",
            str(value).strip().lower(),
        )

    def _equivalent(self, a, b):
        return (
            self._normalize_for_comparison(a)
            == self._normalize_for_comparison(b)
        )

    def _append_unique(self, target, item):
        if self._is_empty(item):
            return

        normalized = self._normalize_for_comparison(item)

        for existing in target:
            if (
                self._normalize_for_comparison(existing)
                == normalized
            ):
                return

        target.append(item)

    @staticmethod
    def _short(value, limit=220):
        text = re.sub(
            r"\s+",
            " ",
            str(value).strip(),
        )

        if len(text) <= limit:
            return text

        return text[:limit - 3] + "..."

    @staticmethod
    def _looks_like_susep_process(value):
        if value is None:
            return False

        text = str(value).strip().lower()

        if not text:
            return False

        if "susep" in text:
            return True

        # Formato muito comum de Processo SUSEP:
        # 15414.901016/2017-01
        return bool(
            re.fullmatch(
                r"\d{5}\.\d{6}/\d{4}-\d{2}",
                text,
            )
        )

    # =========================================================
    # JSON ROBUSTO
    # =========================================================

    @classmethod
    def _parse_json(cls, s):
        if not s:
            raise ValueError(
                "O modelo retornou uma resposta vazia."
            )

        if not isinstance(s, str):
            raise ValueError(
                "O modelo retornou conteúdo em formato inesperado."
            )

        s = s.strip()

        # Remove cercas markdown sem depender de a resposta inteira estar
        # perfeitamente cercada.
        s = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\s*```\s*$",
            "",
            s,
        )

        # 1) JSON direto.
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 2) Localiza o primeiro objeto JSON balanceado. Isso evita o antigo
        # comportamento de pegar simplesmente da primeira { à última }.
        candidate = cls._extract_balanced_object(s)

        if candidate:
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

            # 3) Reparos conservadores, sem tentar "inventar" conteúdo.
            repaired = cls._repair_common_json(candidate)

            try:
                data = json.loads(repaired)
                if isinstance(data, dict):
                    print(
                        "[ExtractionAgent] JSON recuperado por reparo local."
                    )
                    return data
            except json.JSONDecodeError as e:
                raise ValueError(
                    "O modelo retornou JSON malformado e o reparo local "
                    f"não foi suficiente: {e}"
                ) from e

        raise ValueError(
            "O modelo não retornou um objeto JSON válido."
        )

    @staticmethod
    def _extract_balanced_object(text):
        start = text.find("{")

        if start < 0:
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

                if depth == 0:
                    return text[start:index + 1]

        return None

    @staticmethod
    def _repair_common_json(text):
        repaired = text.strip()

        # Remove caracteres de controle inválidos fora de \n, \r e \t.
        repaired = "".join(
            char
            for char in repaired
            if ord(char) >= 32 or char in "\n\r\t"
        )

        # Remove vírgula antes de fechamento de objeto/lista.
        repaired = re.sub(
            r",\s*([}\]])",
            r"\1",
            repaired,
        )

        # Alguns modelos inserem ``` dentro do próprio conteúdo.
        repaired = repaired.replace("```json", "")
        repaired = repaired.replace("```JSON", "")
        repaired = repaired.replace("```", "")

        return repaired
