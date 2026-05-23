from __future__ import annotations

import csv
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "sample_labeled_jobs.csv"
ARTIFACT = ROOT / "artifacts" / "baseline_model.joblib"


def load_dataset(path: Path = DATASET) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def main() -> None:
    texts, labels = load_dataset()
    stratify = labels if len(set(labels)) > 1 and min(labels.count(label) for label in set(labels)) >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.35,
        random_state=42,
        stratify=stratify,
    )

    model = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=4000)),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    print("Accuracy:", round(accuracy_score(y_test, predictions), 3))
    print("\nPrecision / Recall / F1:")
    print(classification_report(y_test, predictions, zero_division=0))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions, labels=sorted(set(labels))))
    print("Labels:", sorted(set(labels)))

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT)
    print(f"\nSaved model to {ARTIFACT}")


if __name__ == "__main__":
    main()

