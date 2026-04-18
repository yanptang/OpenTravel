# OpenTravel Local CLI (V1)

This is a local-first travel planning agent prototype.

It supports:

- request input validation before generation
- slot-based itinerary JSON generation
- plan validation with rule checks
- refine pass (optional, via local LLM)
- interactive slot editing in terminal
- export to JSON and human-readable text

Required request fields include:

- `origin_city`
- `destination`
- `start_date`
- `end_date`
- `arrival_mode`
- `travelers`
- `transport_mode`
- `must_do`

## 1) Setup

```bash
cd 02.LocalAgentCLI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you use local Ollama + LiteLLM, make sure your local model is available.

## 2) Run with local model

```bash
python main.py --input sample_request.json --edit
```

Default model config:

- model: `ollama/qwen3.5:4b`
- api base: `http://localhost:11434`
- max tokens: `4096`
- timeout: `900s`

Override when needed:

```bash
python main.py --model ollama/qwen3.5:4b --api-base http://localhost:11434 --edit
```

If model generation is slow for long trips, tune:

```bash
python main.py --model ollama/qwen3.5:4b --max-tokens 1200 --timeout-sec 900 --edit
```

## 3) Run without model (mock mode)

```bash
python main.py --input sample_request.json --no-llm --edit
```

This is useful when your model is unavailable. The tool still generates a complete itinerary structure.

## 4) Output files

- `outputs/plan.json`: structured itinerary
- `outputs/plan.txt`: readable day-by-day guide

## 5) Interactive edit commands

```text
help
show
show day <n>
delete <day> <slot_id>
set <day> <slot_id> <field> <value>
done
```

Example:

```text
set 3 2 title Drive to glacier base camp
set 3 2 time_start 08:30
delete 5 4
done
```

## 6) Current v1 validation rules

- required request fields present
- valid request date range
- each day has slots
- each day ends with a hotel slot
- slot time format is `HH:MM`
- slot time range must be increasing
- no slot overlap per day
- must-do preferences must appear in generated content

## 7) Suggested next steps

1. add per-day budget cap checks
2. add distance/time heuristics checks
3. add persistent user profile memory (JSON/SQLite)
4. add tool adapters for map/flight/hotel APIs when budget allows
