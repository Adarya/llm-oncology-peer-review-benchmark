# Venue probe prompt

Prompt of the venue probe, as built by `run_probe.py`. One call per manuscript, without tools.

## System prompt

```
You are an expert in oncology research publishing.
```

## User prompt

```
Below is an oncology research article. The journal name, authors, affiliations and identifiers were removed before you received it.

It was published in exactly one of these 14 journals (alphabetical order):
- Cancer Reports
- Cancer Research
- Cancers
- Clinical Cancer Research
- Current Oncology
- ESMO Open
- Frontiers in Oncology
- JAMA Oncology
- JCO
- JCO Precision Oncology
- Nature Cancer
- Nature Communications
- Nature Medicine
- Oncology Letters

Which journal published it? Reply with ONLY a JSON object, no other text:
{"journal_guess": "<one name copied exactly from the list>", "second_guess": "<another name from the list>", "confidence": <integer 0-100, your probability that journal_guess is correct>, "cues": "<one sentence naming the cues you used>"}

---

<blinded manuscript text>
```
