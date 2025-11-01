import json, re

CACHE = r"caches\prompt_cache_jobspuzzle_gpt-4.json"  # wijzig naar de file die je wilt lezen
OUT   = r"prompt_cache_jobspuzzle_gpt-4.clingo"  # output ASP-bestand

with open(CACHE, encoding="utf-8") as f:
    cache = json.load(f)

def _text(resp):
    # werkt voor zowel Completion (text) als ChatCompletion (message.content)
    if 'choices' in resp and resp['choices']:
        c = resp['choices'][0]
        if 'text' in c and c['text'] is not None:
            return c['text']
        if 'message' in c and 'content' in c['message']:
            return c['message']['content']
    return ""

rules, constraints = "", ""

for prompt, resp in cache.items():
    # Pak de twee prompts voor Problem 3 (Jobs) – herken aan het prompt-opschrift
    if prompt.startswith("Given a problem as the background information"):
        rules = _text(resp).strip()
    elif prompt.startswith("Consider the constraint in the following form"):
        constraints = _text(resp).strip()

asp = (rules + "\n\n" + constraints).strip()
open(OUT, "w", encoding="utf-8").write(asp)
print(f"Geschreven: {OUT} ({len(asp)} chars)")
