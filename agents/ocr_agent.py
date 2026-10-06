from pathlib import Path
import fitz
from PIL import Image
import pytesseract
import os
import io


class OCRAgent:
    def __init__(self):
        cmd = os.getenv("TESSERACT_CMD", "").strip()

        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

    def extract(self, path: Path):
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._pdf(path)

        return self._image(path)

    def _image(self, path):
        img = Image.open(path).convert("RGB")

        return pytesseract.image_to_string(
            img,
            lang="por+eng"
        ).strip()

    def _pdf(self, path):
        doc = fitz.open(path)
        chunks = []

        try:
            for i, page in enumerate(doc):
                page_number = i + 1

                # -------------------------------------------------
                # 1. Tenta primeiro extrair o texto nativo.
                #
                # sort=True ajuda a manter uma ordem de leitura
                # mais coerente em PDFs com múltiplos blocos.
                # -------------------------------------------------

                native_text = page.get_text(
                    "text",
                    sort=True
                ).strip()

                text = native_text
                method = "TEXTO NATIVO"

                # -------------------------------------------------
                # 2. Página com pouco texto:
                # tenta OCR como segunda fonte.
                #
                # Não descartamos automaticamente o texto nativo.
                # Depois comparamos os dois resultados.
                # -------------------------------------------------

                if len(native_text) < 200:

                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False
                    )

                    img = Image.open(
                        io.BytesIO(
                            pix.tobytes("png")
                        )
                    ).convert("RGB")

                    ocr_text = pytesseract.image_to_string(
                        img,
                        lang="por+eng"
                    ).strip()

                    # ---------------------------------------------
                    # 3. Escolhe o resultado mais completo.
                    #
                    # Isso evita substituir uma camada nativa útil
                    # por um OCR pior.
                    # ---------------------------------------------

                    if len(ocr_text) > len(native_text):

                        text = ocr_text
                        method = "OCR"

                    elif native_text:

                        text = native_text
                        method = "TEXTO NATIVO"

                    elif ocr_text:

                        text = ocr_text
                        method = "OCR"

                    else:

                        text = ""
                        method = "SEM TEXTO"

                # -------------------------------------------------
                # Marcador explícito da página.
                #
                # O \f é importante porque o ExtractionAgent usa
                # esse caractere para dividir o documento mantendo
                # os limites das páginas.
                # -------------------------------------------------

                chunks.append(
                    f"--- PÁGINA {page_number} "
                    f"[{method}] ---\n{text}"
                )

        finally:
            doc.close()

        return "\f".join(chunks)