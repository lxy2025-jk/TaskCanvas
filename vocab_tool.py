#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英语单词学习工具"""

import io
import sys

# Windows 终端 UTF-8 支持
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stdin.encoding != "utf-8":
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

import sqlite3
import datetime
import random
from pathlib import Path

DB_PATH = Path(__file__).parent / "vocab.db"

# 艾宾浩斯记忆曲线复习间隔（天）
EBBINGHAUS_INTERVALS = [1, 2, 4, 7, 15, 30]


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            definition TEXT NOT NULL,
            created_at DATE NOT NULL,
            next_review_at DATE NOT NULL,
            review_stage INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            review_date DATE NOT NULL,
            mode TEXT NOT NULL,
            correct INTEGER NOT NULL,
            FOREIGN KEY (word_id) REFERENCES words(id)
        )
    """)
    conn.commit()
    conn.close()


def add_word(word, definition):
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(
        "INSERT INTO words (word, definition, created_at, next_review_at, review_stage) VALUES (?, ?, ?, ?, ?)",
        (word, definition, today, today, 0),
    )
    conn.commit()
    conn.close()
    print(f"  [OK] 已录入: {word} -> {definition}")


def get_words_for_review():
    """获取复习用单词：优先到期单词，不足则随机补充"""
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute(
        "SELECT id, word, definition FROM words WHERE next_review_at <= ? ORDER BY next_review_at",
        (today,),
    )
    due_words = c.fetchall()

    if len(due_words) < 5:
        c.execute(
            "SELECT id, word, definition FROM words WHERE next_review_at > ? ORDER BY RANDOM() LIMIT ?",
            (today, 10 - len(due_words)),
        )
        extra = c.fetchall()
        due_words.extend(extra)

    conn.close()
    return due_words


def update_after_review(word_id, correct):
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT review_stage FROM words WHERE id = ?", (word_id,))
    current_stage = c.fetchone()[0]

    if correct:
        new_stage = min(current_stage + 1, len(EBBINGHAUS_INTERVALS))
    else:
        new_stage = 0

    if new_stage < len(EBBINGHAUS_INTERVALS):
        interval = EBBINGHAUS_INTERVALS[new_stage]
        next_review = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()
        hint = f"  [OK] {interval}天后（{next_review}）需复习"
    else:
        next_review = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        hint = "  [OK] 已达最高阶段，30天后再次复习"

    c.execute(
        "UPDATE words SET review_stage = ?, next_review_at = ? WHERE id = ?",
        (new_stage, next_review, word_id),
    )
    conn.commit()
    conn.close()

    if correct:
        print(f"  {hint}")
    else:
        print(f"  [NO] 不正确，已重置复习阶段")


def run_review_session(words, mode):
    """执行一轮复习会话"""
    if not words:
        print("  还没有单词，请先录入！")
        return

    mode_label = "看单词 -> 回忆释义" if mode == "word_to_def" else "看释义 -> 回忆单词"
    print(f"\n  【{mode_label}】本轮共 {len(words)} 个（输入 q 退出）")
    print("  " + "-" * 40)

    total = 0
    correct_count = 0

    for wid, word, definition in words:
        total += 1
        print(f"\n  --- {total}/{len(words)} ---")

        if mode == "word_to_def":
            print(f"  单词: {word}")
            user_input = input("  释义: ").strip()
            answer = definition
        else:
            print(f"  释义: {definition}")
            user_input = input("  单词: ").strip()
            answer = word

        if user_input.lower() == "q":
            total -= 1
            break

        is_correct = user_input.lower() == answer.lower()
        if is_correct:
            correct_count += 1

        update_after_review(wid, is_correct)

        if not is_correct:
            print(f"  正确答案: {answer}")

        # 记录日志
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO review_log (word_id, review_date, mode, correct) VALUES (?, ?, ?, ?)",
            (wid, datetime.date.today().isoformat(), mode, 1 if is_correct else 0),
        )
        conn.commit()
        conn.close()

    if total > 0:
        pct = correct_count / total * 100
        print(f"\n  本轮: {correct_count}/{total} 正确 ({pct:.1f}%)")


def add_words_interactive():
    print("\n  【录入单词】（回车直接输入下一组，空单词结束）")
    print("  格式: 单词 释义（用空格或 Tab 隔开）")
    print("  示例: hello 你好")
    print("  " + "-" * 40)
    while True:
        line = input("  > ").strip()
        if not line:
            break
        parts = line.split(None, 1)
        if len(parts) < 2:
            print("  格式错误！请用空格隔开单词和释义")
            continue
        word, definition = parts
        add_word(word, definition)


def review_mode_a():
    run_review_session(get_words_for_review(), "word_to_def")


def review_mode_b():
    run_review_session(get_words_for_review(), "def_to_word")


def weekly_stats():
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=6)

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    weekday_labels = ["一", "二", "三", "四", "五", "六", "日"]

    print(f"\n  【一周统计】{week_ago} ~ {today}")
    print("  " + "-" * 50)
    print(f"  {'日期':<14} {'星期':<6} {'新学':<8} {'复习':<8} {'正确率':<8}")
    print("  " + "-" * 50)

    total_new = 0
    total_reviews = 0
    total_correct = 0

    for i in range(7):
        day = week_ago + datetime.timedelta(days=i)
        day_str = day.isoformat()
        weekday = weekday_labels[day.weekday()]
        label = "今天" if i == 6 else f"周{weekday}"

        c.execute("SELECT COUNT(*) FROM words WHERE created_at = ?", (day_str,))
        new_words = c.fetchone()[0]
        total_new += new_words

        c.execute(
            "SELECT COUNT(*), COALESCE(SUM(correct), 0) FROM review_log WHERE review_date = ?",
            (day_str,),
        )
        row = c.fetchone()
        review_count = row[0]
        correct_count = row[1]
        total_reviews += review_count
        total_correct += correct_count

        accuracy = correct_count / review_count * 100 if review_count > 0 else 0
        accuracy_str = f"{accuracy:.1f}%" if review_count > 0 else "-"

        print(f"  {day_str:<14} {label:<6} {new_words:<8} {review_count:<8} {accuracy_str:<8}")

    # 总计
    total_accuracy = total_correct / total_reviews * 100 if total_reviews > 0 else 0
    print("  " + "-" * 50)
    print(f"  {'合计':<14} {'':<6} {total_new:<8} {total_reviews:<8} {total_accuracy:.1f}%")

    conn.close()


def review_reminder():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    today = datetime.date.today().isoformat()
    next_week = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

    c.execute(
        "SELECT word, definition, review_stage FROM words WHERE next_review_at <= ? ORDER BY next_review_at",
        (today,),
    )
    due_words = c.fetchall()

    c.execute(
        "SELECT word, definition, next_review_at, review_stage FROM words WHERE next_review_at > ? AND next_review_at <= ? ORDER BY next_review_at",
        (today, next_week),
    )
    upcoming = c.fetchall()

    conn.close()

    print(f"\n  【复习提醒】（艾宾浩斯记忆曲线）")
    print("  " + "-" * 40)

    if due_words:
        print(f"\n  [!] 今天到期（{len(due_words)} 个）:")
        for w, d, stage in due_words:
            print(f"    {w:<18} -> {d}")
    else:
        print("\n  [OK] 今天没有到期的单词")

    if upcoming:
        print(f"\n  [~] 即将到期（{len(upcoming)} 个）:")
        for w, d, date, stage in upcoming:
            days_left = (datetime.date.fromisoformat(date) - datetime.date.today()).days
            print(f"    {w:<18} -> {d:<24} [{days_left}天后]")

    print()


def random_review():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM words")
    total = c.fetchone()[0]
    conn.close()

    if total == 0:
        print("  还没有单词，请先录入！")
        return

    print("\n  【随机抽选】")
    try:
        count_input = input("  抽取数量（默认 10 个）: ").strip()
        count = int(count_input) if count_input else 10
        count = min(count, total)
    except ValueError:
        count = min(10, total)

    print("  模式: 1. 看单词记释义  2. 看释义记单词")
    mode_choice = input("  请选择 (1/2，默认 1): ").strip()
    mode = "word_to_def" if mode_choice != "2" else "def_to_word"

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(
        "SELECT id, word, definition FROM words ORDER BY RANDOM() LIMIT ?",
        (count,),
    )
    words = c.fetchall()
    conn.close()

    run_review_session(words, mode)


def show_menu():
    print("\n" + "=" * 40)
    print("  英语单词学习工具")
    print("=" * 40)

    # 显示待复习提醒
    conn = sqlite3.connect(str(DB_PATH))
    today = datetime.date.today().isoformat()
    due = conn.execute(
        "SELECT COUNT(*) FROM words WHERE next_review_at <= ?", (today,)
    ).fetchone()[0]
    conn.close()
    if due > 0:
        print(f"  [!] {due} 个单词待复习！")

    print("\n  1. 录入单词")
    print("  2. 复盘A：看单词记释义")
    print("  3. 复盘B：看释义记单词")
    print("  4. 一周统计")
    print("  5. 复习提醒")
    print("  6. 随机抽选")
    print("  7. 退出")
    print("-" * 40)


def main():
    init_db()

    while True:
        show_menu()
        choice = input("  请选择 (1-7): ").strip()

        if choice == "1":
            add_words_interactive()
        elif choice == "2":
            review_mode_a()
        elif choice == "3":
            review_mode_b()
        elif choice == "4":
            weekly_stats()
        elif choice == "5":
            review_reminder()
        elif choice == "6":
            random_review()
        elif choice == "7":
            print("\n  加油，明天见！\n")
            break
        else:
            print("  无效选项，请重新选择。")


if __name__ == "__main__":
    main()
