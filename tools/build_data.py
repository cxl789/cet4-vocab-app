# -*- coding: utf-8 -*-
"""
生成 app 内置数据：
  data/cet4.json      —— 四级词汇本（词 + 音标 + 词性 + 中文释义 + 例句 + 真题例句 + 所属单元）
  data/families.json  —— 词典级词族库（WordNet 派生关系）+ 单词 → 词族 映射 + 直接派生近亲

词族构建思路（关键）：
  WordNet 的 `@`（derivationally related form，派生相关形式）指针构成的是一张**全连通大图**，
  直接求传递闭包会把几乎所有单词并成一个巨族（act / action / a / ... 全混一起）。
  因此这里只在**四级词集合内部**建图：每条边都是词典里真实存在的派生关系，
  再求连通分量，得到的就是教材意义上的"词族"（act / action / active / actor 一族）。

用法：
  python tools/build_data.py --cet4-dir <含 CET4_*.json 的目录> --wordnet-zip <wordnet.zip>
依赖：仅标准库。
"""

import argparse
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# ---------------------------------------------------------------- 四级词库

def build_cet4(cet4_dir: str) -> list:
    """读取 kajweb/dict 导出的 CET4_*.json（JSON Lines），合并去重"""
    entries = {}
    for fn in sorted(os.listdir(cet4_dir)):
        if not fn.lower().endswith(".json"):
            continue
        path = os.path.join(cet4_dir, fn)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                head = d.get("headWord", "").strip().lower()
                if not head or head in entries:
                    continue
                c = d["content"]["word"]["content"]

                trans = []
                for t in c.get("trans", []):
                    cn = (t.get("tranCn") or "").strip()
                    pos = (t.get("pos") or "").strip()
                    if cn:
                        trans.append((pos, cn))
                if not trans:
                    continue

                ph = (c.get("ukphone") or c.get("usphone") or "").strip()

                ex = []
                for s in c.get("sentence", {}).get("sentences", [])[:2]:
                    if s.get("sContent") and s.get("sCn"):
                        ex.append([s["sContent"].strip(), s["sCn"].strip()])

                exam = []
                for s in c.get("realExamSentence", {}).get("sentences", [])[:1]:
                    if s.get("sContent") and s.get("sCn"):
                        exam.append([s["sContent"].strip(), s["sCn"].strip()])

                entries[head] = {
                    "w": head,
                    "ph": ph,
                    "cn": "；".join(f"[{p}] {c}" if p else c for p, c in trans[:2]),
                    "pos": trans[0][0],
                    "ex": ex,
                    "exam": exam,
                    "unit": d.get("bookId", fn.replace(".json", "")),
                    "rank": d.get("wordRank", 0),
                }

    return sorted(entries.values(), key=lambda e: (e["unit"], e["rank"]))


# ------------------------------------------------------------ WordNet 词族

class WordNet:
    def __init__(self, wordnet_zip: str):
        import zipfile

        zf = zipfile.ZipFile(wordnet_zip)
        self._lines = {}

        def read(name):
            if name not in self._lines:
                out = []
                for n in zf.namelist():
                    if n.endswith("/" + name):
                        out = zf.read(n).decode("utf-8", "ignore").splitlines()
                        break
                self._lines[name] = out
            return self._lines[name]

        # offset -> (词性, 词列表)
        self.syn_words = {}
        self.syn_pos = {}
        for fn in ("data.noun", "data.verb", "data.adj", "data.adv"):
            for line in read(fn):
                if not line.strip() or line.startswith("  "):
                    continue
                p = line.split()
                try:
                    off = int(p[0])
                    wc = int(p[3])
                except (ValueError, IndexError):
                    continue
                words = [p[4 + 2 * i].replace("_", " ") for i in range(wc)]
                self.syn_words[off] = words
                self.syn_pos[off] = p[2]

    def deriv_edges(self):
        """产出 (源 synset 的词, 目标 synset 的词) 的派生关系对"""
        for fn in ("data.noun", "data.verb", "data.adj", "data.adv"):
            for line in self._lines.get(fn, []):
                if not line.strip() or line.startswith("  "):
                    continue
                p = line.split()
                try:
                    off = int(p[0])
                    wc = int(p[3])
                    pc = int(p[4 + wc * 2])
                except (ValueError, IndexError):
                    continue
                here = self.syn_words.get(off, [])
                idx = 5 + wc * 2
                for _ in range(pc):
                    if idx >= len(p):
                        break
                    sym = p[idx]
                    tgt = p[idx + 1] if idx + 1 < len(p) else None
                    idx += 4
                    if sym != "@" or not (tgt and tgt.isdigit()):
                        continue
                    for t in self.syn_words.get(int(tgt), []):
                        for h in here:
                            yield h, t

    def lemma_links(self):
        """产出 (词形, 同 synset 的词元) 对，用于把变形词挂回原形"""
        for line in self._lines.get("index.sense", []):
            p = line.split()
            if len(p) < 2:
                continue
            word = p[0].split("%")[0].replace("_", " ")
            try:
                off = int(p[1])
            except ValueError:
                continue
            for lm in self.syn_words.get(off, []):
                yield word, lm


# ------------------------------------------------------------ 词干归一（族名解析）

# 常见派生后缀，按长度倒序匹配（长后缀优先）
SUFFIXES = sorted(
    set(
        [
            "ousness", "fulness", "iveness", "ization", "isation", "ational",
            "ically", "ements", "ations", "ially", "ously", "iness", "ition",
            "ation", "ment", "ness", "able", "ible", "ance", "ence", "ical",
            "ial", "ous", "ful", "less", "ship", "hood", "wise", "like", "ally",
            "ion", "ing", "ize", "ise", "ify", "ate", "ish", "ism", "ist",
            "ity", "ety", "ers", "est", "ies", "ied", "ily", "ive", "ively",
            "ed", "es", "er", "or", "ly", "al", "ic", "ar",
            "y", "s",
        ]
    ),
    key=len,
    reverse=True,
)

MIN_STEM = 3


def get_stem(word: str) -> str:
    """剥离派生后缀得到词干：evaluate → evalu，action → act"""
    w = word.lower()
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= MIN_STEM:
            stem = w[: len(w) - len(suf)]
            if suf == "ied":
                stem = stem[:-1] + "y"
            if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                stem = stem[:-1]
            return stem
    return w


def resolve_root(stem: str, cet4: set) -> str:
    """
    把词干解析成族名：
      1) 词干本身就是四级词 → 直接当族名（act）
      2) 否则找词干的最长四级词前缀（activ → act）
      3) 都不行 → 词干本身当族名（evalu、inform）
    """
    if stem in cet4:
        return stem
    for L in range(len(stem), MIN_STEM - 1, -1):
        c = stem[:L]
        if c in cet4:
            return c
    return stem


def build_families(wordnet_zip: str, cet4_words: set) -> tuple:
    wn = WordNet(wordnet_zip)

    # 1) WordNet 直接派生近亲（1 跳，不做传递闭包，避免全连通大图）
    relatives = defaultdict(set)
    for h, t in wn.deriv_edges():
        hl, tl = h.lower(), t.lower()
        if hl in cet4_words and tl in cet4_words and hl != tl:
            relatives[hl].add(tl)
            relatives[tl].add(hl)

    # 2) 词干归一 → 族名
    root_of = {}
    for w in cet4_words:
        root_of[w] = resolve_root(get_stem(w), cet4_words)

    # 2a) 链式归一：族名本身也是四级词、且它另有归属时，跟随一步
    #     factory → factor → fact，三者同族
    for w, r in list(root_of.items()):
        if r != w and r in cet4_words:
            r2 = root_of.get(r)
            if r2 and r2 != r:
                root_of[w] = r2

    # 2b) 用 WordNet 派生近亲合并同族（仅当族名有 ≥4 字母公共前缀，避免误合）
    #     decide / decision → decis
    groups0 = defaultdict(list)
    for w, r in root_of.items():
        groups0[r].append(w)
    by_prefix = defaultdict(list)
    for r in groups0:
        by_prefix[r[:4]].append(r)
    for _, rs in by_prefix.items():
        for i, r1 in enumerate(rs):
            for r2 in rs[i + 1:]:
                linked = any(
                    m2 in relatives.get(m1, ())
                    for m1 in groups0[r1] for m2 in groups0[r2]
                )
                if not linked:
                    continue
                keep = r1 if len(r1) <= len(r2) else r2
                drop = r2 if keep == r1 else r1
                for m in groups0[drop]:
                    root_of[m] = keep
                groups0[keep].extend(groups0.pop(drop))

    # 3) 组装
    groups = defaultdict(list)
    for w, r in root_of.items():
        groups[r].append(w)

    # 4) 词的词性（取 WordNet 中该词所有 synset 的词性集合）
    pos_of = defaultdict(set)
    for off, ws in wn.syn_words.items():
        for x in ws:
            xl = x.lower()
            if xl in cet4_words:
                pos_of[xl].add(wn.syn_pos.get(off, ""))

    families = {}
    word2family = {}
    for root, members in groups.items():
        members = sorted(members, key=lambda s: (len(s), s))
        poses = sorted({p for m in members for p in pos_of.get(m, set())})
        families[root] = {
            "members": members,
            "pos": poses[0] if poses else "",
            "n": len(members),
        }
        for m in members:
            word2family[m] = root

    multi = [v for v in families.values() if v["n"] > 1]
    biggest = sorted(families.items(), key=lambda kv: -kv[1]["n"])[:8]
    print(f"  词族总数: {len(families)}（多词族 {len(multi)}）")
    print(f"  覆盖四级词: {len(word2family)} / {len(cet4_words)}")
    print("  最大族 TOP8: " + ", ".join(f"{k}({v['n']})" for k, v in biggest))
    print(f"  带词典近亲的词: {len(relatives)}")
    return families, word2family, {w: sorted(v) for w, v in relatives.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cet4-dir", required=True)
    ap.add_argument("--wordnet-zip", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "data"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print("== 构建四级词库 ==")
    cet4 = build_cet4(args.cet4_dir)
    print(f"  单词数: {len(cet4)}")
    with open(os.path.join(args.out, "cet4.json"), "w", encoding="utf-8") as f:
        json.dump(cet4, f, ensure_ascii=False, separators=(",", ":"))

    print("== 构建词族库（WordNet 派生关系）==")
    families, word2family, relatives = build_families(
        args.wordnet_zip, {e["w"] for e in cet4}
    )
    with open(os.path.join(args.out, "families.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "families": families,
                "word2family": word2family,
                "relatives": relatives,
            },
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    for fn in ("cet4.json", "families.json"):
        p = os.path.join(args.out, fn)
        print(f"  {fn}: {os.path.getsize(p) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
