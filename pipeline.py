from agents.reception_agent import ReceptionAgent
from agents.ocr_agent import OCRAgent
from agents.extraction_agent import ExtractionAgent
from agents.structure_agent import StructureAgent
from services.database import save_policy


class PolicyPipeline:

    def __init__(self):
        self.reception = ReceptionAgent()
        self.ocr = OCRAgent()
        self.extractor = ExtractionAgent()
        self.structurer = StructureAgent()

    def process(self, uploaded_file, progress_callback=None):

        # 1. Recepção
        if progress_callback:
            progress_callback(
                "recepcao",
                0,
                1,
                "Recebendo documento..."
            )

        path = self.reception.receive(uploaded_file)

        # 2. Extração de texto / OCR
        if progress_callback:
            progress_callback(
                "ocr",
                0,
                1,
                "Extraindo texto do documento..."
            )

        text = self.ocr.extract(path)

        if len(text.strip()) < 30:
            raise ValueError(
                "Não foi possível extrair texto suficiente "
                "do documento."
            )

        if progress_callback:
            progress_callback(
                "ocr",
                1,
                1,
                "Texto extraído com sucesso."
            )

        # 3. Análise por IA
        def extraction_progress(
            completed,
            total,
            message
        ):

            if progress_callback:
                progress_callback(
                    "ia",
                    completed,
                    total,
                    message
                )

        extracted = self.extractor.extract(
            text,
            progress_callback=extraction_progress
        )

        # 4. Estruturação
        if progress_callback:
            progress_callback(
                "estrutura",
                0,
                1,
                "Estruturando informações..."
            )

        structured = self.structurer.normalize(
            extracted
        )

        # 5. Banco de dados
        if progress_callback:
            progress_callback(
                "banco",
                0,
                1,
                "Salvando apólice..."
            )

        policy_id = save_policy(
            uploaded_file.name,
            text,
            structured
        )

        if progress_callback:
            progress_callback(
                "concluido",
                1,
                1,
                "Análise concluída."
            )

        return policy_id, structured