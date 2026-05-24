"""
Future transformer fine-tuning placeholder.

This file is intentionally not required for the hackathon MVP. A teammate can
turn it on later after collecting a larger labeled dataset from analyzed jobs
and user feedback.
"""

from __future__ import annotations


def main() -> None:
    # 1. Replace this path with a real reviewed dataset, for example:
    #    data/labeled_remote_jobs.parquet
    #
    # 2. Load rows with fields like:
    #    - job_description
    #    - legitimacy_label
    #    - remote_authenticity_label
    #    - global_eligibility_label
    #    - job_quality_label
    #
    # 3. Use a Hugging Face model such as "distilbert-base-uncased" or a
    #    domain-specific sentence transformer. Tokenize the descriptions,
    #    split train/validation/test, and fine-tune a multi-label classifier.
    #
    # 4. Save the model under ml/artifacts/transformer_remote_trust/ and add
    #    a lightweight wrapper in scorer.py that only loads it when an
    #    environment variable such as REMOTE_TRUST_USE_TRANSFORMER=true is set.
    #
    # 5. Keep the current rule-based scorer as a fallback so the app remains
    #    usable offline and without paid APIs.
    raise NotImplementedError("Transformer fine-tuning is a future extension.")


if __name__ == "__main__":
    main()

