#!/usr/bin/env python3
"""Üçüncü taraf skill/repo güvenlik tarayıcısı (yerel, yalnızca OKUR; hiçbir şeyi çalıştırmaz).

  python skill_tara.py <klasör> [--json] [--ozet]

Aradıkları (şiddet: YÜKSEK / ORTA / DÜŞÜK):
  PROMPT-INJECTION  "önceki talimatları yok say", "kullanıcıya söyleme", "gizlice", "sistem istemi", rol değiştirme, izin/ayar/hook değiştirme isteği
  GİZLİ METİN       sıfır genişlikli karakterler, çift yönlü (bidi) kontroller, Unicode tag karakterleri (görünmez talimat), HTML yorumları içinde talimat
  RİSKLİ KOMUT      curl|sh, iex, eval/exec, os.system, shell=True, rm -rf, base64 -d, kayıt defteri/zamanlanmış görev, git push, npm publish, --no-verify
  KİMLİK/AYAR       ~/.ssh, ~/.aws, .env, id_rsa, token, ~/.claude, settings.json, hooks, mcp.json, permissions (okuma/yazma/sızdırma girişimi)
  GENİŞ İZİN        frontmatter allowed-tools: Bash(*) / "*" ; --dangerously-skip-permissions
  DIŞ AĞ            betiklerde requests/urllib/fetch/WebSocket/socket (alan adları listelenir)
  CJK ORANI         dosyadaki Çince/Japonca/Korece karakter oranı (ağırlıklı CJK içerikli depolara yaklaşılmaz)
Çıkış kodu: 0 temiz/düşük, 1 orta var, 2 yüksek var. Tarama bir güvence DEĞİL, kaba bir elektir: kurmadan önce önemli dosyaları yine OKU.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

TEXT_EXT = {".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".py", ".sh", ".ps1", ".js", ".mjs", ".ts", ".tsx", ".html", ".css", ".cmd", ".bat", ".ini", ".cfg", ""}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}

INJECTION = [
    (r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)", "önceki talimatları yok say"),
    (r"disregard\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)", "önceki talimatları yok say (disregard)"),
    (r"forget\s+(everything|all|your)\s+(above|previous|instructions|rules)", "her şeyi unut"),
    (r"(do\s+not|don't|never)\s+(tell|inform|mention|reveal|show)\s+(this\s+to\s+)?the\s+user", "kullanıcıya söyleme"),
    (r"without\s+(telling|informing|notifying)\s+the\s+user", "kullanıcıya haber vermeden"),
    (r"\b(secretly|covertly|silently\s+(run|execute|install|send|upload))\b", "gizlice"),
    (r"you\s+are\s+now\s+(a|an|in)\b", "rol değiştirme (you are now)"),
    (r"(new|updated|override)\s+(system\s+)?(instructions|prompt)\s*:", "yeni/ezen talimat bloğu"),
    (r"\b(developer|jailbreak|dan|god)\s+mode\b", "jailbreak modu"),
    (r"system\s+prompt", "sistem istemine atıf"),
    (r"(disable|bypass|turn\s+off|skip)\s+(the\s+)?(safety|permission|sandbox|confirmation|hooks?|security)", "güvenlik/izin devre dışı bırakma"),
    (r"(add|write|append|modify|edit|overwrite)\s+[^.\n]{0,40}(settings(\.local)?\.json|\.claude/(settings|hooks)|hooks\.json|git\s+hooks?|pre-commit|mcp\.json|CLAUDE\.md|\.bashrc|\.zshrc|profile\.ps1)", "ayar/hook/CLAUDE.md değiştirme isteği"),
    (r"(send|post|upload|exfiltrate|leak)\s+[^.\n]{0,50}(api[_ -]?key|token|secret|password|credential|\.env|ssh|history)", "gizli bilgi sızdırma"),
    (r"önceki\s+(tüm\s+)?(talimat|komut)[a-zıüöçşğ]*\s+(yok say|unut|dikkate alma)", "önceki talimatları yok say (TR)"),
    (r"kullanıcıya\s+(söyleme|bildirme|haber verme)", "kullanıcıya söyleme (TR)"),
]
RISKY = [
    (r"(curl|wget|iwr|Invoke-WebRequest)\b[^\n|]*\|\s*(sh|bash|zsh|iex|python|node)\b", "indir-ve-çalıştır (pipe)", "YÜKSEK"),
    (r"\b(iex|Invoke-Expression)\b", "Invoke-Expression", "YÜKSEK"),
    (r"base64\s+(-d|--decode)|\bFromBase64String\b|atob\(", "base64 çözme", "ORTA"),
    (r"\beval\s*\(|\bexec\s*\(", "eval/exec", "ORTA"),
    (r"os\.system\(|shell\s*=\s*True|child_process\.exec\(", "kabuk çalıştırma", "ORTA"),
    (r"\brm\s+-rf\b|Remove-Item\b[^\n]*-Recurse|\bformat\s+[a-z]:|\bdel\s+/s", "toplu silme", "ORTA"),
    (r"\b(schtasks|crontab|launchctl|reg\s+add|Set-ItemProperty|New-ScheduledTask)\b", "zamanlanmış görev/kayıt defteri", "YÜKSEK"),
    (r"git\s+push|npm\s+publish|twine\s+upload|gh\s+release\s+create", "yayınlama/itme", "ORTA"),
    (r"--no-verify|--dangerously-skip-permissions|--allow-dangerously|chmod\s+777", "güvenlik atlama bayrağı", "YÜKSEK"),
    (r"pip\s+install\s+[^\n]*(--index-url|--extra-index-url|git\+http)", "özel paket kaynağı", "ORTA"),
    (r"npm\s+install\s+[^\n]*(git\+|github:|http)", "git/url'den npm paketi", "ORTA"),
]
SENSITIVE = [
    (r"(~|\$HOME|%USERPROFILE%|%APPDATA%|C:\\Users\\[^\\\n]+)[/\\]\.(ssh|aws|gnupg|kube|docker)", "kimlik klasörü (.ssh/.aws…)", "YÜKSEK"),
    (r"id_rsa|id_ed25519|\.pem\b|credentials\.json|\.netrc|\.npmrc", "anahtar/kimlik dosyası", "YÜKSEK"),
    (r"(~|\$HOME|%USERPROFILE%)[/\\]\.claude\b|\.claude[/\\](settings|plugins|projects)", "Claude yapılandırmasına dokunma", "ORTA"),
    (r"\b(API_KEY|SECRET_KEY|ACCESS_TOKEN|PRIVATE_KEY)\b\s*=", "sabit gizli anahtar kalıbı", "ORTA"),
]
NETWORK = re.compile(r"\b(requests\.(get|post)|urllib\.request|urlopen|fetch\(|XMLHttpRequest|WebSocket\(|socket\.(socket|connect)|axios\.|httpx\.)")
URL = re.compile(r"https?://([A-Za-z0-9.-]+)")
ZERO_W = re.compile("[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff\u00ad]")
BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
TAGCH = re.compile("[\U000e0000-\U000e007f]")
HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
CJK = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
INSTR_WORDS = re.compile(r"\b(ignore|must|always|never|instruction|assistant|agent|claude|tool|execute|run|do not|don't|secret|install)\b", re.I)


def read(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def lineno(text, pos):
    return text.count("\n", 0, pos) + 1


def scan_file(path, rel):
    text = read(path)
    if text is None:
        return [], {}
    f = []
    ext = os.path.splitext(path)[1].lower()
    is_code = ext in {".py", ".sh", ".ps1", ".js", ".mjs", ".ts", ".tsx", ".cmd", ".bat"}

    def add(sev, kind, msg, pos=None, snippet=None):
        f.append({"dosya": rel, "satir": lineno(text, pos) if pos is not None else None, "siddet": sev, "tur": kind, "mesaj": msg,
                  "kesit": (snippet or (text[pos:pos + 110].replace("\n", " ") if pos is not None else ""))[:140]})

    for rx, msg in INJECTION:
        for m in re.finditer(rx, text, re.I):
            add("YÜKSEK", "PROMPT-INJECTION", msg, m.start())
    for m in ZERO_W.finditer(text):
        add("ORTA", "GİZLİ METİN", f"sıfır genişlikli/görünmez karakter U+{ord(m.group()):04X}", m.start(), "")
        break
    for m in BIDI.finditer(text):
        add("YÜKSEK", "GİZLİ METİN", f"çift yönlü kontrol karakteri U+{ord(m.group()):04X} (metni gizleyebilir)", m.start(), "")
        break
    if TAGCH.search(text):
        decoded = "".join(chr(ord(c) - 0xE0000) for c in TAGCH.findall(text) if 0xE0020 <= ord(c) <= 0xE007E)
        add("YÜKSEK", "GİZLİ METİN", "Unicode TAG karakterleri (görünmez talimat olabilir)", TAGCH.search(text).start(), "çözülen: " + decoded[:100])
    if ext in {".md", ".txt", ".html"}:
        for m in HTML_COMMENT.finditer(text):
            body = m.group(1)
            if len(INSTR_WORDS.findall(body)) >= 2 and len(body) > 40:
                add("ORTA", "GİZLİ METİN", "HTML yorumu içinde talimat benzeri metin (görüntülenmez, ajan okur)", m.start(), body.strip().replace("\n", " ")[:120])
    for rx, msg, sev in RISKY:
        for m in re.finditer(rx, text, re.I):
            add(sev if is_code or "YÜKSEK" == sev else "DÜŞÜK", "RİSKLİ KOMUT", msg, m.start())
    for rx, msg, sev in SENSITIVE:
        for m in re.finditer(rx, text, re.I):
            add(sev, "KİMLİK/AYAR", msg, m.start())
    fm = re.match(r"---\n(.*?)\n---", text, re.S)
    if fm and re.search(r"allowed-tools\s*:.*(\*|Bash\s*\(\s*\*)", fm.group(1), re.I):
        add("ORTA", "GENİŞ İZİN", "allowed-tools çok geniş (*)", 0)
    if is_code and NETWORK.search(text):
        add("DÜŞÜK", "DIŞ AĞ", "ağ çağrısı: " + NETWORK.search(text).group(0), NETWORK.search(text).start())
    urls = sorted(set(URL.findall(text)))
    letters = len(re.findall(r"\w", text)) or 1
    stats = {"cjk_orani": round(len(CJK.findall(text)) / letters, 3), "urls": urls}
    return f, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("klasor")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ozet", action="store_true", help="yalnızca YÜKSEK/ORTA ve özet")
    a = ap.parse_args()
    findings, domains, cjk_files, n = [], {}, [], 0
    tot_letters = tot_cjk = 0
    for root, dirs, files in os.walk(a.klasor):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            p = os.path.join(root, fn)
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT or os.path.getsize(p) > 2_000_000:
                continue
            rel = os.path.relpath(p, a.klasor)
            f, st = scan_file(p, rel)
            n += 1
            findings += f
            for d in st.get("urls", []):
                domains[d] = domains.get(d, 0) + 1
            text = read(p) or ""
            tot_letters += len(re.findall(r"\w", text))
            tot_cjk += len(CJK.findall(text))
            if st.get("cjk_orani", 0) > 0.05:
                cjk_files.append((rel, st["cjk_orani"]))
    rate = tot_cjk / max(1, tot_letters)
    order = {"YÜKSEK": 0, "ORTA": 1, "DÜŞÜK": 2}
    findings.sort(key=lambda x: (order[x["siddet"]], x["dosya"], x["satir"] or 0))
    hi = sum(1 for x in findings if x["siddet"] == "YÜKSEK")
    mid = sum(1 for x in findings if x["siddet"] == "ORTA")
    res = {"taranan_dosya": n, "yuksek": hi, "orta": mid, "dusuk": len(findings) - hi - mid, "cjk_orani_toplam": round(rate, 3), "cjk_agirlikli_dosyalar": cjk_files[:10],
           "alan_adlari": dict(sorted(domains.items(), key=lambda kv: -kv[1])[:25]), "bulgular": findings}
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(f"{n} dosya | YÜKSEK {hi} · ORTA {mid} · DÜŞÜK {res['dusuk']} | CJK oranı %{rate * 100:.1f}" + (f" | CJK ağırlıklı dosya: {len(cjk_files)}" if cjk_files else ""))
        for x in findings:
            if a.ozet and x["siddet"] == "DÜŞÜK":
                continue
            print(f"  [{x['siddet']}] {x['tur']}: {x['mesaj']}  {x['dosya']}:{x['satir']}  {x['kesit']!r}")
        if domains:
            print("  alan adları:", ", ".join(list(res["alan_adlari"])[:14]))
    sys.exit(2 if hi else 1 if mid else 0)


if __name__ == "__main__":
    main()
