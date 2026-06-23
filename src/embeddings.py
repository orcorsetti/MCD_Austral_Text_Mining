"""Wrapper de SentenceTransformer con encoding normalizado (dot product = coseno)."""
import numpy as np
import torch
from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    """Encapsula un SentenceTransformer cargado una sola vez."""

    def __init__(self, model_name: str) -> None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str]) -> np.ndarray:
        """Codifica textos a array float32 normalizado."""
        return self.model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )
