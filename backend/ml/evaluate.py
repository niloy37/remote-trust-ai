from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.metrics import classification_report, confusion_matrix

try:
    from .train_baseline import ARTIFACT, load_dataset
except ImportError:  # Allows `python ml/evaluate.py` during quick local experiments.
    from backend.ml.train_baseline import ARTIFACT, load_dataset


def main(model_path: Path = ARTIFACT) -> None:
    texts, labels = load_dataset()
    model = joblib.load(model_path)
    predictions = model.predict(texts)
    print(classification_report(labels, predictions, zero_division=0))
    print(confusion_matrix(labels, predictions, labels=sorted(set(labels))))


if __name__ == "__main__":
    main()
