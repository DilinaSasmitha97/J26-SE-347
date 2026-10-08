# NL-to-SQL Service (Member 1)

FastAPI gateway for the schema-aware NL-to-SQL engine.

## Run
```powershell
python -m venv venv; .\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # add an LLM API key
python run_server.py     # http://localhost:8000/docs
```

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness + active LLM |
| GET | `/api/v1/schema?db_id=default\|nemsuerp` | Schema DDL |
| POST | `/api/v1/translate` | NL -> SQL (`user_query`, `injected_rules`, optional `schema_meta`) |
| POST | `/api/v1/ask` | NL -> SQL -> executes, returns rows |
| POST | `/api/v1/extract-schema` | Pruned schema only |

See [team_interface_contract.md](team_interface_contract.md) for the request/response contract.
Smoke test: `python test_fastapi_endpoints.py`.

## Notes
- The demo gateway forwards only `user_query` and `injected_rules`. Rules are the
  pasted JSON object (or `null`); legacy text rules remain accepted. The service
  serializes JSON into its prompt without adding gateway policy or Vonara hints.
- The service console prints complete translation traces with a request ID:
  received input, engine input, schema, entity grounding, relationship/join hints,
  pruning, exemplars, full model request/prompt, raw model output, token usage,
  validation/refinement attempts, final SQL and HTTP response/errors. Model
  request logging excludes API keys and request headers. These traces are printed
  by default for translation requests. Watch the NL-to-SQL terminal opened by
  `demo-application/start-all.bat`.
- Copied from `NL TO SQL prototype` (left untouched). `profiler.py` was absent in the prototype and was reconstructed.
- Few-shot exemplars need `SPIDER_TRAIN_PATH`; they are silently disabled otherwise.
