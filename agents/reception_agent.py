from pathlib import Path
import re, uuid

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

class ReceptionAgent:
    def receive(self, uploaded_file):
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix not in ALLOWED:
            raise ValueError(f"Formato não suportado: {suffix}")
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(uploaded_file.name).name)
        path = Path("data/uploads")
        path.mkdir(parents=True, exist_ok=True)
        dest = path / f"{uuid.uuid4().hex}_{safe}"
        dest.write_bytes(uploaded_file.getvalue())
        return dest
