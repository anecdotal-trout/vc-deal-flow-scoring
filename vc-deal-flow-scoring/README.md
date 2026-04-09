# VC Deal Flow Scoring Model

Scores and ranks startup investment opportunities on a weighted composite framework. Built for VC analysts managing a pipeline of inbound deals who need a consistent, quantitative way to triage and prioritise.

## What it does

- Scores each deal across 7 dimensions: team, market size, traction, unit economics, momentum, defensibility, and capital efficiency
- Ranks the full pipeline by composite score
- Analyses deal source quality (referral vs inbound vs conference vs cold outreach)
- Compares advancing deals to declined ones to identify what predicts success
- Benchmarks valuations by stage
- Generates sourcing and triage recommendations

## Quick start

```bash
pip install -r requirements.txt
python deal_scorer.py
```

## Scoring framework

| Dimension | Weight | Signal |
|-----------|--------|--------|
| Team | 25% | Founder experience, domain expertise, prior exits |
| Traction | 20% | ARR growth rate |
| Unit economics | 15% | Gross margin + net revenue retention |
| Market | 15% | TAM (log-scaled — diminishing returns above $50B) |
| Momentum | 10% | Customer count + product-market fit signal |
| Defensibility | 10% | Moat type: proprietary model > network effects > data > integrations > none |
| Capital efficiency | 5% | Runway remaining |

Weights are configurable in the code. The current set reflects a typical early-stage (seed/Series A) evaluation where team and traction matter most.

## Data

`/data/deal_flow.csv` contains 20 deals across AI, fintech, cybersecurity, climate tech, and other sectors. Each deal includes quantitative metrics (ARR, growth, margins, burn) and qualitative assessments (team score, moat type, PMF status).

## Key insight from the sample data

Referral-sourced deals advance at roughly 3x the rate of cold outreach. Team score is the single strongest predictor of whether a deal advances — advancing deals average ~8.1 vs ~6.1 for declined. This is consistent with what most early-stage VCs report anecdotally, but the model makes it quantifiable.

## Tech

- **Python** — pandas + numpy for scoring model and derived metrics
- **SQL** (SQLite) — pipeline aggregations, source analysis, sector breakdowns

## Other projects

- [startup-comp-screener](https://github.com/anecdotal-trout/startup-comp-screener) — Startup comparable screening and ranking
- [cohort-retention-analysis](https://github.com/anecdotal-trout/cohort-retention-analysis) — User cohort retention tables
- [b2b-pipeline-analyzer](https://github.com/anecdotal-trout/b2b-pipeline-analyzer) — Marketing spend → pipeline ROI
