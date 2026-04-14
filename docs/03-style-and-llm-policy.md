# Aiker Style and LLM Policy

## Language policy

Everything should be written in English:

- source code
- prompts
- database field names
- log messages
- report templates
- CLI help text
- error messages
- Markdown exports

This removes ambiguity, improves prompt consistency, and keeps the operator workflow aligned with the tool ecosystem used in Kali and modern security engineering.

## Coding style

Recommended standards:

- Python 3.12+
- typed code everywhere
- Pydantic for validated schemas
- SQLAlchemy or SQLModel for persistence
- Typer for CLI
- Rich for terminal rendering
- Ruff for linting
- Pytest for tests
- no notebook magics
- no Colab-only imports
- no mixed-language identifiers

## ReAct style

Aiker should be a tool-using agent, not a chat bot that emits shell strings blindly.

The loop should follow this pattern:

1. `Goal`
2. `Relevant context`
3. `Action selection`
4. `Tool call`
5. `Observation`
6. `Memory update`
7. `Next step or stop`

Important implementation note:

- The system may internally use reasoning to choose the next action.
- The application should store a brief `reasoning_summary`, not raw hidden chain-of-thought.
- Observations, tool results, and decisions should remain inspectable by the operator.

## Hallucination control policy

The agent must be conservative by design.

Recommended defaults:

- primary model: `qwen/qwen3.6-plus` via OpenRouter
- temperature: `0.0` to `0.01`
- top_p: `0.2` to `0.4`
- response format: structured JSON
- tool choice: `auto` only for registered tools
- max iterations per run: `6` to `10`
- force explicit uncertainty when evidence is weak

The agent must never:

- invent open ports
- invent services
- invent credentials
- invent hostnames
- invent OS guesses without evidence
- invent vulnerability confirmations without a matching observation

The agent should always:

- cite the tool observation that supports a claim
- prefer enumeration before exploitation
- pursue escalation or authenticated validation only when prior evidence makes the path credible
- avoid repeating the same failed tool call without new evidence
- prefer evidence-backed summaries over fluent prose

## OpenRouter policy

Use the OpenAI-compatible SDK with OpenRouter as the provider gateway.

Recommended base configuration:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
```

Recommended request defaults:

```python
{
    "model": "qwen/qwen3.6-plus",
    "temperature": 0.01,
    "top_p": 0.2,
    "response_format": {"type": "json_object"},
}
```

## Prompting policy

The system prompt should define:

- internal authorized pentest context
- scope restrictions
- evidence-first reasoning
- aggressive but evidence-bound assessment behavior
- tool-first execution
- refusal to fabricate unsupported findings
- requirement to store structured observations after each step
- direct JSON-only output contract
- escalation intent as a validated objective, not an assumption

The task prompt should include:

- current project
- current objective
- planning profile such as `web`, `network`, or `ad`
- current asset or host
- short-term memory summary
- relevant long-term facts
- situational state
- available tools
- recent failures or blocked paths

Prompt tone should be:

- direct
- technical
- decisive
- non-theatrical
- aggressive in coverage, but not destructive or fictional

Profile guidance should adapt by surface:

- `web`: bias toward HTTP/TLS, path discovery, fingerprinting, WAF detection, and web validation tooling
- `network`: bias toward DNS, ports, protocol exposure, service validation, and network reachability
- `ad`: bias toward SMB, LDAP, domain clues, share exposure, and credential-supported validation paths

## Tool output policy

Every tool should return structured output with:

- `status`
- `summary`
- `raw_output`
- `artifacts`
- `facts_extracted`
- `confidence`

This lets the memory layer operate on stable data instead of scraping free-form text after the fact.

## Operator experience style

The CLI should feel operational, not academic:

- compact tables
- colored status markers
- explicit current project header
- explicit current host or objective
- expandable raw output
- visible evidence path or evidence ID

The agent should sound precise, calm, and technical, not verbose or theatrical.
