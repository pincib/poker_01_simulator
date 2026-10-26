# Backend tests

Run the full automated suite from the repository root:

```powershell
python -m unittest discover -s backend/tests -v
```

Coverage includes game state, evaluation, equity and performance benchmarks,
opponent decisions, coaching, API behavior, PLO exact-two-card rules, pot-limit
sizing, Omaha wraps, and self-play chip/rake accounting. The roadmap's larger
50,000-hand check runs with:

```powershell
python scripts/run_phase7_verification.py
```
