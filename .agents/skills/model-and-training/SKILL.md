---
name: model-and-training
description: Modify or review NEWXAU models, artifacts, training, validation, or Kronos integration with leakage, reproducibility, and fallback safeguards.
---

# Model and Training

1. Read model runtime/ensemble code, training code, tests, and artifact documentation.
2. Review feature order, artifact contracts, provenance, and missing/invalid-artifact fallback.
3. Do not edit `vendor/Kronos` or commit model weights, caches, or downloaded artifacts unless explicitly authorized.
4. Prevent leakage and look-ahead bias; keep train, validation, test, and walk-forward periods separate.
5. Record reproducible metrics, dataset/timeframe ranges, seeds, and hardware assumptions.
6. Do not claim profitability from training loss alone; require out-of-sample evidence.
7. Run focused offline tests, sync memory, and run the checker.
