"""Reranking biomedico de los candidatos del shortlist con MedCPT-Cross-Encoder.

El cross-encoder lee el par (consulta, documento del estudio) en conjunto. MedCPT
esta entrenado para reranking biomedico (query -> articulo), a diferencia del
ms-marco generico que no discrimina sobre texto clinico. Es el paso 'Score General'.
"""
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

RERANK_MODEL_NAME = 'ncbi/MedCPT-Cross-Encoder'
MAX_LENGTH = 512


class CrossEncoderReranker:
    """Encapsula MedCPT-Cross-Encoder cargado una sola vez; devuelve logits de relevancia."""

    def __init__(self, model_name: str = RERANK_MODEL_NAME) -> None:
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device).eval()

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Logit de relevancia por par (consulta, documento del estudio)."""
        if not pairs:
            return []
        enc = self.tokenizer(
            [[q, d] for q, d in pairs],
            truncation=True, padding=True, max_length=MAX_LENGTH, return_tensors='pt',
        ).to(self.device)
        with torch.no_grad():
            logits = self.model(**enc).logits.squeeze(-1)
        return logits.cpu().tolist()
