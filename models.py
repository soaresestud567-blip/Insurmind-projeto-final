from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any

@dataclass
class PolicyData:
    seguradora: Optional[str] = None
    segurado: Optional[str] = None
    numero_apolice: Optional[str] = None
    vigencia_inicio: Optional[str] = None
    vigencia_fim: Optional[str] = None
    moeda: Optional[str] = None
    limite_responsabilidade: Optional[str] = None
    limite_agregado: Optional[str] = None
    franquia: Optional[str] = None
    premio: Optional[str] = None
    coberturas: List[Dict[str, Any]] = field(default_factory=list)
    exclusoes: List[Dict[str, Any]] = field(default_factory=list)
    extensoes: List[Dict[str, Any]] = field(default_factory=list)
    definicoes_relevantes: List[Dict[str, Any]] = field(default_factory=list)
    clausulas_relevantes: List[Dict[str, Any]] = field(default_factory=list)
    observacoes: List[str] = field(default_factory=list)
    evidencias: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
