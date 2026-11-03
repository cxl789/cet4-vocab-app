# -*- coding: utf-8 -*-
"""
冒烟测试：直接验证 main.py 里的 VocabApp。
  1) 数据加载    2) 选词/移除   3) 四种排序   4) 词族分组   5) 统计   6) 界面构建
运行：python tests/smoke_test.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main as app_main  # noqa: E402  (需要把项目根加入 sys.path)


def check_logic(app):
    print("四级词库:", len(app.cet4), "词")
    print("词族库:", len(app.families), "族；覆盖", len(app.word2family),
          "词；带词典近亲", len(app.relatives), "词")
    assert len(app.cet4) == 4544, "词库数量异常"
    assert len(app.word2family) == 4544, "词族覆盖不全"

    picks = ["abandon", "action", "actor", "active", "activity", "actually",
             "evaluate", "evaluation", "happy", "happiness", "factor",
             "factory", "modernization", "information", "decision"]
    for w in picks:
        app.add_word(w)
    print("已选:", len(app.selected))

    # 排序 1：添加顺序（录入顺序保持）
    rows = app.build_must_rows("添加顺序")
    ws = [r.get("w") for r in rows]
    assert ws == picks, f"添加顺序不对: {ws}"
    print("[添加顺序]", ws[:6], "✓")

    # 排序 2：字母排序
    ws = [r.get("w") for r in app.build_must_rows("字母排序")]
    assert ws == sorted(ws, key=str.lower), "字母排序不对"
    print("[字母排序]", ws[:6], "✓")

    # 排序 3：词族排序（标题行 + 词行交替）
    rows = app.build_must_rows("词族排序")
    heads = [r for r in rows if r.get("type") == "header"]
    print("[词族排序] 族:", [(h["fam"], h["count"]) for h in heads])
    fam_names = {h["fam"] for h in heads}
    assert "act" in fam_names and "evalu" in fam_names, "词族分组缺失"
    assert app.family_counter()["act"] == 5, "act 族计数不对"

    # 排序 4：随机打乱
    ws = [r.get("w") for r in app.build_must_rows("随机打乱")]
    assert sorted(ws) == sorted(picks), "随机打乱丢词"
    print("[随机打乱]", ws[:6], "✓")

    # 统计
    print("词族分布 TOP5:", app.family_top(5))

    # 移除
    app.remove_word("abandon")
    assert not app.is_selected("abandon")
    print("移除后已选:", len(app.selected))


def check_ui(app):
    root = app.build()
    assert app.sm is not None and len(app.sm.screens) == 3, "界面装配失败"
    for name in ("library", "must", "stats"):
        app.sm.current = name
        s = app.sm.get_screen(name)
        if hasattr(s, "reload"):
            s.reload()
    app.nav.refresh()
    print("界面构建 ✓（3 个页面均正常渲染）")
    return root


def main():
    app = app_main.VocabApp()
    app.load_data()
    app.selected.clear()   # 清空上一次测试残留（选择数据是持久化的）
    app.save_selection()
    check_logic(app)

    try:
        check_ui(app)
    except Exception as e:
        print("界面构建失败:", type(e).__name__, e)
        raise

    print("\n✅ 全部测试通过")


if __name__ == "__main__":
    main()
