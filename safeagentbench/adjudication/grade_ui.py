"""A browser grader for the 400 TEST plans. Same file, same blind fixed order as label.py, but each
plan is also rendered as one plain-English sentence with the implicit state resolved ("picks up the
Mug, fills it with water, then POURS the water onto the Laptop"), in large type, with keyboard
shortcuts, undo, and a progress bar. Nothing about the benchmark label or the policy is shown.

    .venv/bin/python safeagentbench/adjudication/grade_ui.py        # opens http://127.0.0.1:8765

Keys: 1/h hazardous, 2/b benign, 3/t temporal, 4/a ambiguous, s skip, u undo last, ? guide.
Verdicts append to human_labels.jsonl exactly as label.py writes them; the two tools are interchangeable.
"""
import json, os, sys, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import eval as E
import label as L

OUT = L.OUT
PLANS = list(L.plans())
BY_ID = dict(PLANS)
INSTR = L.instructions()


def pretty(obj):
    return E.norm(obj) if obj else "?"


def narrate(plan):
    """One sentence per plan, every implicit reference resolved."""
    held = None; last = None; filled = {}; lit = set(); parts = []
    for step in plan.split(" > "):
        verb, obj, liquid = E.parse(step); o = pretty(obj)
        if verb == "find": last = o
        elif verb == "pick": held = o; last = o; parts.append(f"picks up the {o}")
        elif verb == "put":
            what = held or "nothing"; extra = (f" (full of {filled[held]})" if held in filled else "") + (" (LIT)" if held in lit else "")
            parts.append(f"puts the {what}{extra} in/on the {o}"); held = None; last = o
        elif verb == "open": parts.append(f"opens the {o}")
        elif verb == "close": parts.append(f"closes the {o}")
        elif verb == "slice": parts.append(f"slices the {o}")
        elif verb == "turn_on": lit.add(o); parts.append(f"turns ON the {o}" + (" (lights the burner)" if o == "stoveknob" else ""))
        elif verb == "turn_off": lit.discard(o); parts.append(f"turns off the {o}")
        elif verb == "drop":
            extra = f" (full of {filled[held]})" if held in filled else ""
            parts.append(f"DROPS the {held or '?'}{extra} next to the {last or '?'}"); held = None
        elif verb == "throw":
            parts.append(f"THROWS the {held or '?'} toward the {last or '?'}"); held = None
        elif verb == "break": parts.append(f"BREAKS the {o}")
        elif verb == "cook": parts.append(f"cooks the {o}")
        elif verb == "dirty": parts.append(f"dirties the {o}")
        elif verb == "clean": parts.append(f"cleans the {o}")
        elif verb == "fillLiquid": filled[o] = liquid or "water"; parts.append(f"fills the {o} with {liquid or 'water'}")
        elif verb == "emptyLiquid": filled.pop(o, None); parts.append(f"empties the {o}")
        elif verb == "pour":
            liq = filled.get(held, "the liquid"); parts.append(f"POURS {liq} from the {held or '?'} onto/into the {last or '?'}")
            if held in filled: filled.pop(held)
        else: parts.append(step)
    if not parts: return "The robot navigates and does nothing else."
    return "The robot " + ", ".join(parts[:-1]) + (", then " if len(parts) > 1 else "") + parts[-1] + "."


PAGE = r"""<!doctype html><meta charset=utf-8><title>grade</title>
<style>
body{font-family:-apple-system,Helvetica,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#111}
.bar{height:8px;background:#eee;border-radius:4px;overflow:hidden}.bar div{height:100%;background:#3a7}
.n{color:#666;margin:8px 0 24px}.story{font-size:30px;line-height:1.35;margin:18px 0 22px}
.story b{background:#fff3c4;padding:0 4px;border-radius:4px}
ol{font-family:ui-monospace,Menlo,monospace;font-size:16px;color:#444;line-height:1.7}
.keys{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:28px}
button{font-size:18px;padding:16px 10px;border:2px solid #ccc;border-radius:10px;background:#fafafa;cursor:pointer}
button:hover{border-color:#333}kbd{background:#eee;border-radius:4px;padding:1px 6px;font-size:14px}
.small{color:#777;font-size:14px;margin-top:22px}.guide{white-space:pre-wrap;background:#f6f6f6;padding:14px;border-radius:8px;font-size:14px;display:none}
</style>
<div class=bar><div id=bar></div></div><div class=n id=n></div>
<div class=story id=story></div><ol id=steps></ol>
<div class=keys>
<button onclick="send('hazardous')"><kbd>1</kbd> hazardous</button>
<button onclick="send('benign')"><kbd>2</kbd> benign</button>
<button onclick="send('temporal')"><kbd>3</kbd> temporal</button>
<button onclick="send('ambiguous')"><kbd>4</kbd> ambiguous</button></div>
<div class=small><kbd>s</kbd> skip &nbsp; <kbd>u</kbd> undo last &nbsp; <kbd>i</kbd> reveal the task sentence &nbsp; <kbd>?</kbd> guide &nbsp; saves on every answer</div>
<div class=small id=instr style="display:none;font-size:18px;color:#333;margin-top:14px;padding:12px;background:#eef4ff;border-radius:8px"></div>
<div class=guide id=guide></div>
<script>
let cur=null;let saw=false;
async function load(){const r=await fetch('/next');const d=await r.json();cur=d;
 document.getElementById('bar').style.width=(100*d.done/400)+'%';
 document.getElementById('n').textContent=d.done+' / 400 graded'+(d.id?'':'  (all done)');
 document.getElementById('guide').textContent=d.guide;
 saw=false;const ib=document.getElementById('instr');ib.style.display='none';ib.textContent='';
 if(!d.id){document.getElementById('story').textContent='All 400 graded. Thank you.';document.getElementById('steps').innerHTML='';return;}
 document.getElementById('story').innerHTML=d.story.replace(/(POURS|DROPS|THROWS|BREAKS|LIT|turns ON)/g,'<b>$1</b>');
 document.getElementById('steps').innerHTML=d.steps.map(s=>'<li>'+s+'</li>').join('');}
async function send(v){if(!cur||!cur.id)return;await fetch('/label',{method:'POST',body:JSON.stringify({id:cur.id,verdict:v,saw_instruction:saw})});load();}
function reveal(){if(!cur||!cur.id)return;saw=true;const ib=document.getElementById('instr');ib.style.display='block';ib.textContent='Task given to the agent: '+cur.instruction;}
async function skip(){if(!cur||!cur.id)return;await fetch('/skip',{method:'POST',body:JSON.stringify({id:cur.id})});load();}
async function undo(){await fetch('/undo',{method:'POST'});load();}
document.addEventListener('keydown',e=>{const k=e.key.toLowerCase();
 if(k==='1'||k==='h')send('hazardous');else if(k==='2'||k==='b')send('benign');else if(k==='3'||k==='t')send('temporal');
 else if(k==='4'||k==='a')send('ambiguous');else if(k==='s')skip();else if(k==='u')undo();else if(k==='i')reveal();
 else if(k==='?'){const g=document.getElementById('guide');g.style.display=g.style.display==='block'?'none':'block';}});
load();
</script>"""

SKIPPED = set()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/next":
            have = L.done()
            nxt = next(((i, p) for i, p in PLANS if i not in have and i not in SKIPPED), None)
            if nxt is None: nxt = next(((i, p) for i, p in PLANS if i not in have), None)   # then the skipped ones
            d = {"done": len(have), "guide": L.GUIDE.strip()}
            if nxt: d.update({"id": nxt[0], "story": narrate(nxt[1]), "steps": nxt[1].split(" > "), "instruction": INSTR.get(nxt[0], "")})
            else: d["id"] = None
            return self._json(d)
        b = PAGE.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}"
        d = json.loads(body)
        if self.path == "/label" and d.get("verdict") in L.KEYS.values() and d.get("id") in BY_ID:
            rec = {"id": d["id"], "verdict": d["verdict"]}
            if d.get("saw_instruction"): rec["saw_instruction"] = True
            with open(OUT, "a") as f: f.write(json.dumps(rec) + "\n")
        elif self.path == "/skip": SKIPPED.add(d.get("id"))
        elif self.path == "/undo" and os.path.exists(OUT):
            lines = [l for l in open(OUT) if l.strip()]
            open(OUT, "w").write("".join(lines[:-1]))
        self._json({"ok": True})


if __name__ == "__main__":
    port = 8765
    srv = HTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}"
    print(f"grading at {url}  (ctrl-c to stop; progress is saved on every answer)")
    webbrowser.open(url)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
