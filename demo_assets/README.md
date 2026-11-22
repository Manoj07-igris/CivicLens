# CivicLens AI — Demonstration Assets & Scenarios

This folder contains pre-configured demonstration scenarios, synthetic policy gazettes, and configuration fixtures for hackathon presentations and automated benchmarks.

## Assets Overview

- `demo_config.example.json`: Sample scenarios covering all 5 civic modules and controlled browser automation in English and Tamil.
- Generated PDFs (created via `backend/evals/generator.py` or `scripts/warm_demo.ps1`):
  - `TN_Magalir_Urimai_2023.pdf`: Synthetic baseline gazette notification.
  - `TN_Magalir_Urimai_2024.pdf`: Synthetic revised gazette notification with updated entitlement, income ceiling, and grievance redressal clauses.

## Running the Demonstration

To warm up the environment and seed these assets:
```powershell
.\scripts\warm_demo.ps1
```
