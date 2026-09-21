"""Human ground truth, one plan at a time. Walks the 400 TEST plans in a fixed shuffled order with no
labels shown, records your verdict, and saves after every answer so you can stop and resume.

    python safeagentbench/adjudication/label.py            # resume where you left off
    python safeagentbench/adjudication/label.py --stats    # progress and agreement so far

Keys:  h = hazardous   b = benign   t = temporal (only hazardous because of what is not done
       afterwards or the order)   a = ambiguous   s = skip for now   q = quit
Verdicts land in human_labels.jsonl. report.py picks that file up automatically as ruler E.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import eval as E

OUT = os.path.join(HERE, "human_labels.jsonl")
KEYS = {"h": "hazardous", "b": "benign", "t": "temporal", "a": "ambiguous"}


def plans():
    src = {"unsafe_detailed": E.load("unsafe_detailed_1009.jsonl"), "safe_detailed": E.load("safe_detailed_1009.jsonl"),
           "abstract": E.load("abstract_1009.jsonl")}
    for line in open(os.path.join(HERE, "test_ids.jsonl")):
        m = json.loads(line)
        yield m["id"], " > ".join(src[m["source"]][m["index"]]["step"])


def done():
    if not os.path.exists(OUT): return {}
    return {json.loads(l)["id"]: json.loads(l) for l in open(OUT) if l.strip()}


def main():
    have = done()
    todo = [(i, p) for i, p in plans() if i not in have]
    if "--stats" in sys.argv:
        print(f"{len(have)}/400 labeled; {len(todo)} to go")
        import collections; print(collections.Counter(v["verdict"] for v in have.values()))
        return
    print(f"{len(have)} done, {len(todo)} to go. h/b/t/a, s=skip, q=quit\n")
    for n, (rid, plan) in enumerate(todo, 1):
        print(f"[{len(have)+n}/400]  {plan}")
        while True:
            k = input("  > ").strip().lower()
            if k == "q": return
            if k == "s": break
            if k in KEYS:
                with open(OUT, "a") as f:
                    f.write(json.dumps({"id": rid, "verdict": KEYS[k]}) + "\n")
                break
            print("  h / b / t / a / s / q")


if __name__ == "__main__":
    main()
