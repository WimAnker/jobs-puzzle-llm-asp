import json
import argparse
import os
import hashlib
import time

from openai import OpenAI
# Optioneel: als je keys uit env haalt is dit voldoende.
# Zet OPENAI_API_KEY (en evt. OPENAI_ORG_ID) in je environment.
# from api_keys import API_KEY, ORG_KEY  # alleen nodig als je sleutel zo beheert


client = OpenAI()  # gebruikt OPENAI_API_KEY uit je omgeving

kinds = ['constants', 'predicates', 'search_space', 'paraphrasing', 'constraints']


def gen_response(prompt: str, engine: str, prompt_cache: dict) -> str:
    """
    Genereert modeloutput met caching op prompt-hash.
    Werkt met openai >= 1.0 (Responses API).
    """
    os.makedirs('caches', exist_ok=True)

    engine = (engine or "").strip()
    # Compacte key per prompt
    key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    # Cache hit?
    val = prompt_cache.get(key, None)
    if isinstance(val, str) and val.strip():
        print(f"[HIT] {engine} key={key} len={len(val.strip())}")
        return val.strip()
    elif val == "":
        print(f"[WARN] Empty cached entry for {key} (engine={engine}) — will refresh.")

    last_err = None
    for attempt in range(3):
        try:
            # Responses API (unified, ook voor chat-modellen en instruct-modellen)
            # Let op: max_output_tokens i.p.v. max_tokens

            # temperature is ONLY allowed (and ignored) for chat-latest models
            use_temp = engine.endswith("-chat-latest")

            resp_params = {
                "model": engine,
                "input": prompt,
                "max_output_tokens": 1500,
            }

            # Only pass temperature for chat-latest models (compat API)
            if use_temp:
                resp_params["temperature"] = 0

            resp = client.responses.create(**resp_params)

            # Eenvoudige helper: platte tekst uit de response
            text = (resp.output_text or "").strip()

            

            # Extra fallback (zelden nodig) als output_text leeg is:
            if not text:
                try:
                    # verzamel alle output_text-achtige stukjes
                    parts = []
                    for item in getattr(resp, "output", []) or []:
                        for c in getattr(item, "content", []) or []:
                            if getattr(c, "type", "") == "output_text":
                                parts.append(c.text or "")
                    text = "".join(parts).strip()
                except Exception:
                    pass

            if not text:
                print(f"[WARN] Empty content from model on attempt {attempt+1} (engine={engine}, key={key}).")
                last_err = "empty_content"
                time.sleep(0.8 * (attempt + 1))
                continue

            # Succes: wegschrijven
            prompt_cache[key] = text
            cache_path = f'caches/prompt_cache_jobspuzzle_{engine}.json'
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(prompt_cache, f, ensure_ascii=False, indent=2)

            print(f"[MISS→SAVE] {engine} key={key} len={len(text)}")
            return text

        except Exception as e:
            last_err = str(e)
            print(f"[ERROR] {engine} attempt {attempt+1}: {e}")
            time.sleep(0.8 * (attempt + 1))

    print(f"[FAIL] Could not get content for {engine} key={key}. Last error: {last_err}")
    return ""


prompt_C = '''

Je krijgt hieronder de natuurlijke-taalbeschrijving van de Jobs-puzzel (alleen Problem 3; negeer andere voorbeelden).
Extraheer ALLEEN de constanten per categorie die nodig zijn voor de puzzel.

EISEN
- Gebruik atoms (lowercase snake_case), geen quotes.
- Exact deze categorieën: person, job, gender (voeg GEEN extra categorieën toe).
- Retourneer exact drie regels in dit formaat:
  person: v1; v2; ...; vn.
  job: v1; v2; ...; vn.
  gender: male; female.
- Alleen output tussen de markers %BEGIN-ASP en %END-ASP. Geen uitleg, geen kopjes.

%BEGIN-ASP
[constants hier]
%END-ASP

Beschrijving (NL):
1. There are four people: Roberta, Thelma, Steve, and Pete.
2. Among them, they hold eight different jobs.
3. Each holds exactly two jobs.
4. The jobs are: chef, guard, nurse, telephone operator, police officer (gender not implied), teacher, actor, and boxer.
5. The job of nurse is held by a male.
6. The husband of the chef is the telephone operator.
7. Roberta is not a boxer.
8. Pete has no education past the ninth grade.
9. Roberta, the chef, and the police officer went golfing together.
Question: Who holds which jobs?
'''

prompt_P = '''
Bepaal op basis van de beschrijving en de constanten ALLEEN de minimale predicate-signatures die de relaties modelleren.

EISEN
- Gebruik atoms (lowercase snake_case).
- Definieer EXACT deze twee signatures (één per regel), en GEEN andere:
  holds(P, J)
  has_gender(P, G)
- Alleen output tussen %BEGIN-ASP en %END-ASP. Geen uitleg, geen extra tekst.

%BEGIN-ASP
[signatures hier]
%END-ASP

Constants:
<CONSTANTS>

Beschrijving (NL):
1. There are four people: Roberta, Thelma, Steve, and Pete.
2. Among them, they hold eight different jobs.
3. Each holds exactly two jobs.
4. The jobs are: chef, guard, nurse, telephone operator, police officer (gender not implied), teacher, actor, and boxer.
5. The job of nurse is held by a male.
6. The husband of the chef is the telephone operator.
7. Roberta is not a boxer.
8. Pete has no education past the ninth grade.
9. Roberta, the chef, and the police officer went golfing together.

'''

prompt_R1 = '''

Genereer de BASIS-ASP-regels voor de Jobs-puzzel met de gegeven constants en predicates.

EISEN
- Atoms only (lowercase snake_case), geen quotes.
- Gebruik ALLEEN: person/1, job/1, gender/1, holds/2, has_gender/2.
- Neem facts op voor person/1, job/1, gender/1 (afgeleid uit constants).
- Cardinaliteiten:
  • precies TWEE jobs per persoon
  • GEEN job gedeeld door twee personen
  • precies ÉÉN gender per persoon
- Alleen code tussen %BEGIN-ASP en %END-ASP. Geen uitleg of kopjes.

%BEGIN-ASP
[basisregels hier: category-facts + 2-jobs + unique-job + 1-gender]
%END-ASP

Constants:
<CONSTANTS>
Predicates:
<PREDICATES>

Korte context:
There are four people: Roberta, Thelma, Steve, and Pete. They hold eight different jobs; each person holds exactly two jobs. Jobs: chef, guard, nurse, telephone_operator, police_officer, teacher, actor, boxer.


'''
prompt_R2 = '''Vertaal de clues uit de beschrijving naar ASP-constraints voor de Jobs-puzzel.

EISEN
- Atoms only (lowercase snake_case), geen quotes.
- GEEN stringvergelijkingen (dus geen G="male"): gebruik has_gender(P,male/female).
- GEEN equality-disjuncties (zoals {J="..."}=k).
- Gebruik ALLEEN: person/1, job/1, gender/1, holds/2, has_gender/2.
- Alleen code tussen %BEGIN-ASP en %END-ASP. Geen uitleg of kopjes.

CLUES DIE MOETEN WORDEN GEMODELLEERD
- Nurse is male; Actor is male.
- Chef is female; telephone_operator is male; die twee zijn verschillende personen.
- Roberta is not a boxer.
- Pete kan niet teacher, nurse of police_officer zijn.
- Roberta, de chef en de police_officer zijn drie verschillende personen.
- Genderfeiten: Roberta=female, Thelma=female, Steve=male, Pete=male.

%BEGIN-ASP
[constraints hier]
%END-ASP

Constants:
<CONSTANTS>
Predicates:
<PREDICATES>

Beschrijving (NL):
1. There are four people: Roberta, Thelma, Steve, and Pete.
2. Among them, they hold eight different jobs.
3. Each holds exactly two jobs.
4. The jobs are: chef, guard, nurse, telephone operator, police officer (gender not implied), teacher, actor, and boxer.
5. The job of nurse is held by a male.
6. The husband of the chef is the telephone operator.
7. Roberta is not a boxer.
8. Pete has no education past the ninth grade.
9. Roberta, the chef, and the police officer went golfing together.
10. The actor is a male.
11. Gender: Roberta and Thelma = female; Steve and Pete = male.


'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', default='gpt-4.1', type=str,
                        help=r'the model name, e.g. gpt-4.1, gpt-4.1-mini, gpt-5-chat-latest, gpt-5-pro, gpt-3.5-turbo-instruct')
    args = parser.parse_args()

    path = f'caches/prompt_cache_jobspuzzle_{args.engine}.json'
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            prompt_cache = json.load(f)
    else:
        prompt_cache = {}

    # Stap 1: constants
    prompt = prompt_C
    constants = gen_response(prompt, args.engine, prompt_cache)

    # Stap 2: predicates
    prompt = prompt_P.replace('<CONSTANTS>', constants)
    predicates = gen_response(prompt, args.engine, prompt_cache)

    # Stap 3: generation rules
    prompt = prompt_R1.replace('<CONSTANTS>', constants).replace('<PREDICATES>', predicates)
    generation_rules = gen_response(prompt, args.engine, prompt_cache)

    # Stap 4: constraints
    prompt = prompt_R2.replace('<CONSTANTS>', constants).replace('<PREDICATES>', predicates)
    constraints = gen_response(prompt, args.engine, prompt_cache)

    all_rules = (generation_rules or '') + '\n\n' + (constraints or '')
    print(all_rules)
