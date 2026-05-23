# Quickstart: Advanced ML Graph Verification

## Baseline Local Verification

1. Start the backend dependencies that are already required for local operation.

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Seed sample jobs.

   ```bash
   python seed_db.py --reset
   ```

3. Run the backend without Neo4j to verify fallback classification.

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. Submit a sample analysis and verify the response includes:

   - existing `final_score`, `verdict`, and `scores`
   - new `classification.label`
   - new `classification.confidence`
   - top red flags and positive signals
   - remote restriction evidence
   - graph verification status showing fallback or unavailable behavior

## Optional Neo4j Verification

1. Start Docker Compose from the repository root.

   ```bash
   docker compose up --build
   ```

2. Confirm the backend still returns a completed analysis when Neo4j is available.

3. Stop Neo4j or switch graph configuration to unavailable and repeat the same
   analysis. The category should still be returned with degraded graph status.

## Training and Evaluation Workflow

1. Validate the advanced dataset.

   ```bash
   python -m ml.train_advanced --dataset data/sample_advanced_jobs.csv --validate-only
   ```

2. Train local advanced artifacts.

   ```bash
   python -m ml.train_advanced --dataset data/sample_advanced_jobs.csv
   ```

3. Evaluate artifacts.

   ```bash
   python -m ml.evaluate_advanced --dataset data/sample_advanced_jobs.csv
   ```

4. Verify evaluation output includes all five labels, precision, recall, F1,
   confusion matrix, class distribution, and representative misclassifications.

## Frontend Verification

1. Start the frontend.

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. Analyze a verified sample, scam sample, country-restricted sample, and
   hybrid/location-bound sample.

3. Confirm result and detail pages show the new category, confidence, graph
   summary, red flags, positive signals, and remote restriction evidence without
   removing existing score cards.

## Required Test Coverage

- Category assignment for each of the five labels.
- Evidence completeness for every analysis.
- Missing advanced artifacts fallback.
- Neo4j unavailable fallback.
- Conflicting graph relationship warnings.
- Dataset validation failures for unknown labels and missing required columns.
- Evaluation report includes all five categories.
