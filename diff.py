import json, difflib

f1 = r"prompt_cache_jobspuzzle_text-davinci-003_original.clingo"
f2 = r"prompt_cache_jobspuzzle_gpt-3.5-turbo-instruct.clingo"
out = r"diff_gpt3.5.txt"

with open(f1, encoding="utf-8") as a, open(f2, encoding="utf-8") as b:
    j1, j2 = json.load(a), json.load(b)

# sort keys so output is deterministic
s1 = json.dumps(j1, indent=2, sort_keys=True).splitlines()
s2 = json.dumps(j2, indent=2, sort_keys=True).splitlines()

diff = difflib.unified_diff(s1, s2, fromfile=f1, tofile=f2, lineterm="")
with open(out, "w", encoding="utf-8") as f:
    f.writelines(line + "\n" for line in diff)

print(f"✅ Diff saved to {out}")
