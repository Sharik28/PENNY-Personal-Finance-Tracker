"""
╔══════════════════════════════════════════════════════╗
║          PENNY  — Personal Finance Tracker           ║
║       Track • Analyze • Budget • Grow Wealth         ║
╚══════════════════════════════════════════════════════╝
A real-world Python solution for personal expense management.
Features: SQLite persistence, analytics, budget alerts, CSV export, charts.
"""

import sqlite3
import csv
import os
import sys
import json
import datetime
from pathlib import Path
from tabulate import tabulate
from colorama import init, Fore, Back, Style
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import warnings
warnings.filterwarnings("ignore")

init(autoreset=True)

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "penny.db"
EXPORT_DIR = BASE_DIR / "exports"
CHART_DIR  = BASE_DIR / "charts"

EXPORT_DIR.mkdir(exist_ok=True)
CHART_DIR.mkdir(exist_ok=True)

# ─── Color Palette ────────────────────────────────────────────────────────────
C = {
    "header":  Fore.CYAN + Style.BRIGHT,
    "success": Fore.GREEN + Style.BRIGHT,
    "warn":    Fore.YELLOW + Style.BRIGHT,
    "error":   Fore.RED + Style.BRIGHT,
    "accent":  Fore.MAGENTA + Style.BRIGHT,
    "dim":     Fore.WHITE + Style.DIM,
    "bold":    Style.BRIGHT,
    "reset":   Style.RESET_ALL,
}

CATEGORIES = [
    "Food & Dining", "Transport", "Shopping", "Entertainment",
    "Healthcare", "Utilities", "Housing", "Education",
    "Travel", "Savings", "Income", "Other"
]

CATEGORY_EMOJI = {
    "Food & Dining":  "🍽️ ", "Transport":   "🚗 ", "Shopping":    "🛍️ ",
    "Entertainment":  "🎬 ", "Healthcare":  "💊 ", "Utilities":   "💡 ",
    "Housing":        "🏠 ", "Education":   "📚 ", "Travel":      "✈️ ",
    "Savings":        "💰 ", "Income":      "💵 ", "Other":       "📦 "
}

# ─── Database Layer ───────────────────────────────────────────────────────────
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                description TEXT    NOT NULL,
                amount      REAL    NOT NULL,
                type        TEXT    NOT NULL CHECK(type IN ('expense','income')),
                category    TEXT    NOT NULL,
                note        TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT    NOT NULL UNIQUE,
                monthly_limit REAL  NOT NULL,
                created_at  TEXT    DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                target      REAL    NOT NULL,
                saved       REAL    NOT NULL DEFAULT 0,
                deadline    TEXT,
                created_at  TEXT    DEFAULT (date('now'))
            );
        """)

# ─── Display Helpers ──────────────────────────────────────────────────────────
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def banner():
    print(C["header"] + """
╔══════════════════════════════════════════════════════════════╗
║   💸  P E N N Y  —  Personal Finance Tracker  💸            ║
║        Track Smarter. Spend Wiser. Save Better.              ║
╚══════════════════════════════════════════════════════════════╝""")
    now = datetime.datetime.now()
    print(C["dim"] + f"   {now.strftime('%A, %d %B %Y  |  %I:%M %p')}\n")

def section(title):
    print(C["accent"] + f"\n{'─'*60}")
    print(C["accent"] + f"  {title}")
    print(C["accent"] + f"{'─'*60}")

def fmt_amount(amount, tx_type=None):
    if tx_type == "income":
        return C["success"] + f"₹{amount:,.2f}" + C["reset"]
    elif tx_type == "expense":
        return C["error"] + f"₹{amount:,.2f}" + C["reset"]
    return C["bold"] + f"₹{amount:,.2f}" + C["reset"]

def input_float(prompt, min_val=0.01):
    while True:
        try:
            val = float(input(prompt).strip())
            if val < min_val:
                print(C["warn"] + f"  ⚠ Value must be ≥ {min_val}")
                continue
            return val
        except ValueError:
            print(C["error"] + "  ✗ Invalid number. Try again.")

def pick_from_list(prompt, items, allow_back=True):
    for i, item in enumerate(items, 1):
        emoji = CATEGORY_EMOJI.get(item, "  ")
        print(f"  {C['bold']}{i:>2}.{C['reset']} {emoji}{item}")
    if allow_back:
        print(f"  {C['dim']} 0.  ← Back{C['reset']}")
    while True:
        try:
            choice = int(input(f"\n{prompt}").strip())
            if allow_back and choice == 0:
                return None
            if 1 <= choice <= len(items):
                return items[choice - 1]
            print(C["warn"] + "  ⚠ Invalid choice.")
        except ValueError:
            print(C["error"] + "  ✗ Enter a number.")

# ─── Core Operations ──────────────────────────────────────────────────────────
def add_transaction():
    section("➕  ADD TRANSACTION")
    tx_type = None
    print(f"  {C['bold']}1.{C['reset']} 💵 Income")
    print(f"  {C['bold']}2.{C['reset']} 💸 Expense")
    while True:
        try:
            t = int(input("\n  Type [1/2]: ").strip())
            if t in (1, 2):
                tx_type = "income" if t == 1 else "expense"
                break
        except ValueError:
            pass
        print(C["warn"] + "  ⚠ Enter 1 or 2.")

    desc = input("  Description: ").strip()
    if not desc:
        print(C["warn"] + "  ⚠ Description cannot be empty.")
        return

    amount = input_float("  Amount (₹): ")

    date_str = input("  Date [YYYY-MM-DD, blank=today]: ").strip()
    if not date_str:
        date_str = datetime.date.today().isoformat()
    else:
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            print(C["error"] + "  ✗ Invalid date format.")
            return

    print("\n  Select category:")
    category = pick_from_list("  Choice: ", CATEGORIES)
    if category is None:
        return

    note = input("  Note (optional): ").strip()

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (date, description, amount, type, category, note) VALUES (?,?,?,?,?,?)",
            (date_str, desc, amount, tx_type, category, note)
        )

    print(C["success"] + f"\n  ✔ Transaction added! {fmt_amount(amount, tx_type)} [{category}]")
    _check_budget_alert(category, date_str[:7])

def _check_budget_alert(category, month):
    with get_conn() as conn:
        budget = conn.execute(
            "SELECT monthly_limit FROM budgets WHERE category=?", (category,)
        ).fetchone()
        if not budget:
            return
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions "
            "WHERE category=? AND type='expense' AND strftime('%Y-%m',date)=?",
            (category, month)
        ).fetchone()[0]

    limit = budget[0]
    pct = (spent / limit) * 100 if limit > 0 else 0
    if pct >= 100:
        print(C["error"] + f"\n  🚨 BUDGET EXCEEDED for {category}! Spent ₹{spent:,.0f} / ₹{limit:,.0f} ({pct:.0f}%)")
    elif pct >= 80:
        print(C["warn"] + f"\n  ⚠  Budget warning for {category}: {pct:.0f}% used (₹{spent:,.0f} / ₹{limit:,.0f})")

def view_transactions():
    section("📋  TRANSACTIONS")
    print("  Filter by:")
    print(f"  {C['bold']}1.{C['reset']} This month")
    print(f"  {C['bold']}2.{C['reset']} This year")
    print(f"  {C['bold']}3.{C['reset']} Last 30 days")
    print(f"  {C['bold']}4.{C['reset']} All time")
    print(f"  {C['bold']}5.{C['reset']} By category")
    print(f"  {C['dim']} 0.  ← Back{C['reset']}")

    try:
        choice = int(input("\n  Filter: ").strip())
    except ValueError:
        return

    today = datetime.date.today()
    where = "1=1"
    params = []

    if choice == 1:
        where = "strftime('%Y-%m', date) = ?"
        params = [today.strftime("%Y-%m")]
    elif choice == 2:
        where = "strftime('%Y', date) = ?"
        params = [str(today.year)]
    elif choice == 3:
        cutoff = (today - datetime.timedelta(days=30)).isoformat()
        where = "date >= ?"
        params = [cutoff]
    elif choice == 4:
        pass
    elif choice == 5:
        print("\n  Select category:")
        cat = pick_from_list("  Choice: ", CATEGORIES)
        if cat is None:
            return
        where = "category = ?"
        params = [cat]
    elif choice == 0:
        return

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, date, description, amount, type, category, note "
            f"FROM transactions WHERE {where} ORDER BY date DESC LIMIT 50",
            params
        ).fetchall()

    if not rows:
        print(C["warn"] + "\n  No transactions found.")
        return

    headers = ["ID", "Date", "Description", "Amount", "Type", "Category", "Note"]
    table = []
    for r in rows:
        color = Fore.GREEN if r[4] == "income" else Fore.RED
        table.append([
            r[0], r[1],
            r[2][:28] + "…" if len(r[2]) > 28 else r[2],
            color + f"₹{r[3]:,.2f}" + Style.RESET_ALL,
            color + r[4].capitalize() + Style.RESET_ALL,
            CATEGORY_EMOJI.get(r[5], "") + r[5],
            r[6][:20] if r[6] else ""
        ])

    print("\n" + tabulate(table, headers=headers, tablefmt="rounded_outline"))
    print(C["dim"] + f"\n  Showing {len(rows)} records.")

def view_dashboard():
    section("📊  FINANCIAL DASHBOARD")
    today = datetime.date.today()
    month = today.strftime("%Y-%m")

    with get_conn() as conn:
        # Monthly summary
        income = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income' AND strftime('%Y-%m',date)=?", (month,)
        ).fetchone()[0]
        expenses = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense' AND strftime('%Y-%m',date)=?", (month,)
        ).fetchone()[0]
        total_income = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income'").fetchone()[0]
        total_expenses = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense'").fetchone()[0]
        tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        cat_breakdown = conn.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE type='expense' AND strftime('%Y-%m',date)=? GROUP BY category ORDER BY 2 DESC",
            (month,)
        ).fetchall()
        budgets = conn.execute("SELECT category, monthly_limit FROM budgets").fetchall()

    net = income - expenses
    net_color = C["success"] if net >= 0 else C["error"]
    savings_rate = (net / income * 100) if income > 0 else 0

    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │  {C['bold']}THIS MONTH  ({today.strftime('%B %Y')}){C['reset']}
  │
  │  {C['success']}Income   ₹{income:>12,.2f}{C['reset']}
  │  {C['error']}Expenses ₹{expenses:>12,.2f}{C['reset']}
  │  {net_color}Net      ₹{net:>12,.2f}{C['reset']}   Savings rate: {savings_rate:.1f}%
  │
  │  {C['bold']}ALL TIME{C['reset']}
  │  Total Income:   ₹{total_income:>12,.2f}
  │  Total Expenses: ₹{total_expenses:>12,.2f}
  │  Net Worth Δ:    ₹{total_income - total_expenses:>12,.2f}
  │  Transactions:   {tx_count:>5}
  └─────────────────────────────────────────────────────┘""")

    if cat_breakdown:
        print(C["bold"] + "\n  Top Spending This Month:")
        budget_dict = dict(budgets)
        cat_data = []
        for cat, amt in cat_breakdown[:7]:
            limit = budget_dict.get(cat)
            bar_len = min(int((amt / (expenses or 1)) * 30), 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            pct = (amt / expenses * 100) if expenses > 0 else 0
            budget_info = ""
            if limit:
                used_pct = amt / limit * 100
                budget_info = (C["error"] if used_pct >= 100 else C["warn"] if used_pct >= 80 else C["success"]) + \
                              f"  [{used_pct:.0f}% of ₹{limit:,.0f} budget]" + C["reset"]
            emoji = CATEGORY_EMOJI.get(cat, "  ")
            print(f"  {emoji}{cat:<18} {Fore.CYAN}{bar}{C['reset']} {pct:5.1f}%  ₹{amt:>10,.2f}{budget_info}")

def manage_budgets():
    section("🎯  BUDGET MANAGER")
    print(f"  {C['bold']}1.{C['reset']} Set / Update budget")
    print(f"  {C['bold']}2.{C['reset']} View all budgets")
    print(f"  {C['bold']}3.{C['reset']} Delete budget")
    print(f"  {C['dim']} 0.  ← Back{C['reset']}")

    try:
        choice = int(input("\n  Choice: ").strip())
    except ValueError:
        return

    if choice == 1:
        print("\n  Select category to budget:")
        cat = pick_from_list("  Choice: ", CATEGORIES)
        if cat is None:
            return
        limit = input_float(f"  Monthly limit for {cat} (₹): ")
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO budgets (category, monthly_limit) VALUES (?,?) "
                "ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit",
                (cat, limit)
            )
        print(C["success"] + f"\n  ✔ Budget set: {cat} → ₹{limit:,.2f}/month")

    elif choice == 2:
        month = datetime.date.today().strftime("%Y-%m")
        with get_conn() as conn:
            budgets = conn.execute("SELECT category, monthly_limit FROM budgets ORDER BY category").fetchall()
            if not budgets:
                print(C["warn"] + "\n  No budgets set yet.")
                return
            rows = []
            for cat, limit in budgets:
                spent = conn.execute(
                    "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE category=? AND type='expense' AND strftime('%Y-%m',date)=?",
                    (cat, month)
                ).fetchone()[0]
                remaining = limit - spent
                pct = (spent / limit * 100) if limit > 0 else 0
                status = "🔴 OVER" if pct >= 100 else "🟡 WARN" if pct >= 80 else "🟢 OK"
                rows.append([CATEGORY_EMOJI.get(cat,"") + cat, f"₹{limit:,.2f}",
                              f"₹{spent:,.2f}", f"₹{remaining:,.2f}", f"{pct:.0f}%", status])
        print("\n" + tabulate(rows, headers=["Category","Limit","Spent","Remaining","Used","Status"],
                              tablefmt="rounded_outline"))

    elif choice == 3:
        print("\n  Select category to remove budget:")
        cat = pick_from_list("  Choice: ", CATEGORIES)
        if cat is None:
            return
        with get_conn() as conn:
            conn.execute("DELETE FROM budgets WHERE category=?", (cat,))
        print(C["success"] + f"\n  ✔ Budget removed for {cat}.")

def manage_goals():
    section("🏆  SAVINGS GOALS")
    print(f"  {C['bold']}1.{C['reset']} Add goal")
    print(f"  {C['bold']}2.{C['reset']} Update progress")
    print(f"  {C['bold']}3.{C['reset']} View all goals")
    print(f"  {C['dim']} 0.  ← Back{C['reset']}")

    try:
        choice = int(input("\n  Choice: ").strip())
    except ValueError:
        return

    if choice == 1:
        name = input("  Goal name (e.g. Emergency Fund): ").strip()
        if not name:
            print(C["error"] + "  ✗ Name required.")
            return
        target = input_float("  Target amount (₹): ")
        saved = input_float("  Already saved (₹, 0 if none): ", min_val=0)
        deadline = input("  Deadline [YYYY-MM-DD, optional]: ").strip() or None
        with get_conn() as conn:
            conn.execute("INSERT INTO goals (name, target, saved, deadline) VALUES (?,?,?,?)",
                         (name, target, saved, deadline))
        print(C["success"] + f"\n  ✔ Goal '{name}' created! Target: ₹{target:,.2f}")

    elif choice == 2:
        with get_conn() as conn:
            goals = conn.execute("SELECT id, name, target, saved FROM goals").fetchall()
        if not goals:
            print(C["warn"] + "\n  No goals yet.")
            return
        for g in goals:
            pct = (g[3] / g[2] * 100) if g[2] > 0 else 0
            print(f"  {C['bold']}{g[0]}.{C['reset']} {g[1]} — ₹{g[3]:,.0f}/₹{g[2]:,.0f} ({pct:.0f}%)")
        try:
            gid = int(input("\n  Goal ID to update: ").strip())
        except ValueError:
            return
        add = input_float("  Amount to add (₹): ")
        with get_conn() as conn:
            conn.execute("UPDATE goals SET saved = saved + ? WHERE id=?", (add, gid))
            goal = conn.execute("SELECT name, target, saved FROM goals WHERE id=?", (gid,)).fetchone()
        if goal:
            pct = (goal[2] / goal[1] * 100) if goal[1] > 0 else 0
            print(C["success"] + f"\n  ✔ Updated '{goal[0]}': ₹{goal[2]:,.2f}/₹{goal[1]:,.2f} ({pct:.0f}%)")
            if pct >= 100:
                print(C["success"] + "  🎉 GOAL ACHIEVED! Congratulations!")

    elif choice == 3:
        with get_conn() as conn:
            goals = conn.execute("SELECT name, target, saved, deadline, created_at FROM goals").fetchall()
        if not goals:
            print(C["warn"] + "\n  No goals set yet.")
            return
        rows = []
        for g in goals:
            pct = (g[2] / g[1] * 100) if g[1] > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            remaining = g[1] - g[2]
            rows.append([g[0], f"₹{g[1]:,.2f}", f"₹{g[2]:,.2f}", f"₹{remaining:,.2f}",
                         f"{bar} {pct:.0f}%", g[3] or "—"])
        print("\n" + tabulate(rows, headers=["Goal","Target","Saved","Remaining","Progress","Deadline"],
                              tablefmt="rounded_outline"))

def generate_charts():
    section("📈  CHARTS & ANALYTICS")
    today = datetime.date.today()
    month = today.strftime("%Y-%m")

    with get_conn() as conn:
        # Category breakdown this month
        cat_data = conn.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE type='expense' "
            "AND strftime('%Y-%m',date)=? GROUP BY category ORDER BY 2 DESC",
            (month,)
        ).fetchall()

        # Monthly trend (last 6 months)
        trend_data = conn.execute(
            "SELECT strftime('%Y-%m',date) as m, type, SUM(amount) "
            "FROM transactions WHERE date >= date('now','-6 months') "
            "GROUP BY m, type ORDER BY m"
        ).fetchall()

        # Daily expenses this month
        daily_data = conn.execute(
            "SELECT date, SUM(amount) FROM transactions WHERE type='expense' "
            "AND strftime('%Y-%m',date)=? GROUP BY date ORDER BY date",
            (month,)
        ).fetchall()

    fig = plt.figure(figsize=(16, 10), facecolor="#0f0f1a")
    fig.suptitle("PENNY — Financial Analytics Dashboard",
                 fontsize=18, fontweight="bold", color="#e0d7ff",
                 fontfamily="monospace", y=0.98)

    gs = GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35,
                  left=0.06, right=0.97, top=0.92, bottom=0.08)

    COLORS = ["#7c3aed","#06b6d4","#10b981","#f59e0b","#ef4444",
              "#ec4899","#8b5cf6","#3b82f6","#14b8a6","#f97316","#84cc16","#a855f7"]
    BG  = "#0f0f1a"
    GRID_COLOR = "#1e1b4b"
    TEXT_COLOR = "#c4b5fd"

    # ── 1. Donut: category breakdown ──────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(BG)
    if cat_data:
        labels = [CATEGORY_EMOJI.get(c[0],"") + c[0][:12] for c in cat_data]
        sizes  = [c[1] for c in cat_data]
        wedges, texts, autotexts = ax1.pie(
            sizes, labels=labels, autopct="%1.0f%%",
            colors=COLORS[:len(sizes)], startangle=90,
            wedgeprops=dict(width=0.55, edgecolor=BG, linewidth=2),
            textprops=dict(color=TEXT_COLOR, fontsize=7)
        )
        for at in autotexts:
            at.set_fontsize(7)
            at.set_color("#fff")
        ax1.set_title(f"Spending by Category\n({today.strftime('%B %Y')})",
                      color=TEXT_COLOR, fontsize=10, pad=10)
    else:
        ax1.text(0.5, 0.5, "No expense data\nfor this month",
                 ha="center", va="center", color=TEXT_COLOR, fontsize=10, transform=ax1.transAxes)
        ax1.set_title("Spending by Category", color=TEXT_COLOR, fontsize=10)

    # ── 2. Bar: monthly income vs expenses ────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1:])
    ax2.set_facecolor(BG)
    ax2.tick_params(colors=TEXT_COLOR)
    ax2.spines["bottom"].set_color(GRID_COLOR)
    ax2.spines["left"].set_color(GRID_COLOR)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.yaxis.set_tick_params(labelcolor=TEXT_COLOR)
    ax2.xaxis.set_tick_params(labelcolor=TEXT_COLOR)
    ax2.set_facecolor(BG)
    ax2.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    ax2.set_axisbelow(True)

    if trend_data:
        months_set = sorted(set(r[0] for r in trend_data))
        inc_vals = []
        exp_vals = []
        for m in months_set:
            inc = sum(r[2] for r in trend_data if r[0]==m and r[1]=="income")
            exp = sum(r[2] for r in trend_data if r[0]==m and r[1]=="expense")
            inc_vals.append(inc)
            exp_vals.append(exp)

        x = range(len(months_set))
        w = 0.38
        bars1 = ax2.bar([i - w/2 for i in x], inc_vals, width=w,
                        color="#10b981", alpha=0.85, label="Income", zorder=3)
        bars2 = ax2.bar([i + w/2 for i in x], exp_vals, width=w,
                        color="#ef4444", alpha=0.85, label="Expenses", zorder=3)

        display_months = [datetime.datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months_set]
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(display_months, rotation=30, ha="right", fontsize=8)
        ax2.legend(facecolor="#1e1b4b", edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

        for bar in bars1:
            h = bar.get_height()
            if h > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, h + max(inc_vals+exp_vals)*0.01,
                         f"₹{h/1000:.0f}k" if h >= 1000 else f"₹{h:.0f}",
                         ha="center", va="bottom", color="#10b981", fontsize=6.5)
        for bar in bars2:
            h = bar.get_height()
            if h > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, h + max(inc_vals+exp_vals)*0.01,
                         f"₹{h/1000:.0f}k" if h >= 1000 else f"₹{h:.0f}",
                         ha="center", va="bottom", color="#ef4444", fontsize=6.5)
    else:
        ax2.text(0.5, 0.5, "No trend data yet", ha="center", va="center",
                 color=TEXT_COLOR, fontsize=11, transform=ax2.transAxes)

    ax2.set_title("Monthly Income vs Expenses (Last 6 Months)",
                  color=TEXT_COLOR, fontsize=10, pad=10)
    ax2.set_ylabel("Amount (₹)", color=TEXT_COLOR, fontsize=9)

    # ── 3. Line: daily spending this month ────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, :2])
    ax3.set_facecolor(BG)
    ax3.tick_params(colors=TEXT_COLOR)
    for spine in ax3.spines.values():
        spine.set_color(GRID_COLOR)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)
    ax3.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    ax3.set_axisbelow(True)

    if daily_data:
        dates = [d[0] for d in daily_data]
        amounts = [d[1] for d in daily_data]
        avg = sum(amounts) / len(amounts)
        ax3.plot(range(len(dates)), amounts, color="#7c3aed", linewidth=2, zorder=3)
        ax3.fill_between(range(len(dates)), amounts, alpha=0.25, color="#7c3aed")
        ax3.axhline(avg, color="#f59e0b", linestyle="--", linewidth=1, alpha=0.7,
                    label=f"Avg ₹{avg:,.0f}/day")
        step = max(1, len(dates) // 8)
        ax3.set_xticks(range(0, len(dates), step))
        ax3.set_xticklabels([dates[i][-2:] for i in range(0, len(dates), step)],
                             color=TEXT_COLOR, fontsize=8)
        ax3.legend(facecolor="#1e1b4b", edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)
    else:
        ax3.text(0.5, 0.5, "No daily data for this month", ha="center", va="center",
                 color=TEXT_COLOR, fontsize=11, transform=ax3.transAxes)

    ax3.set_title(f"Daily Spending — {today.strftime('%B %Y')}",
                  color=TEXT_COLOR, fontsize=10, pad=10)
    ax3.set_ylabel("Amount (₹)", color=TEXT_COLOR, fontsize=9)
    ax3.set_xlabel("Day of Month", color=TEXT_COLOR, fontsize=9)
    ax3.yaxis.set_tick_params(labelcolor=TEXT_COLOR)

    # ── 4. Horizontal bar: top categories all time ────────────────────────────
    ax4 = fig.add_subplot(gs[1, 2])
    ax4.set_facecolor(BG)
    ax4.tick_params(colors=TEXT_COLOR)
    for spine in ax4.spines.values():
        spine.set_color(GRID_COLOR)
    ax4.spines["top"].set_visible(False)
    ax4.spines["right"].set_visible(False)
    ax4.xaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    ax4.set_axisbelow(True)

    with get_conn() as conn:
        alltime_cat = conn.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE type='expense' "
            "GROUP BY category ORDER BY 2 DESC LIMIT 8"
        ).fetchall()

    if alltime_cat:
        cats_at = [c[0][:14] for c in alltime_cat]
        vals_at = [c[1] for c in alltime_cat]
        bars = ax4.barh(range(len(cats_at)), vals_at,
                        color=COLORS[:len(cats_at)], alpha=0.85)
        ax4.set_yticks(range(len(cats_at)))
        ax4.set_yticklabels(cats_at, color=TEXT_COLOR, fontsize=8)
        ax4.xaxis.set_tick_params(labelcolor=TEXT_COLOR)
        for bar, val in zip(bars, vals_at):
            ax4.text(val + max(vals_at)*0.01, bar.get_y() + bar.get_height()/2,
                     f"₹{val/1000:.1f}k" if val >= 1000 else f"₹{val:.0f}",
                     va="center", color=TEXT_COLOR, fontsize=7.5)
    else:
        ax4.text(0.5, 0.5, "No data yet", ha="center", va="center",
                 color=TEXT_COLOR, transform=ax4.transAxes)

    ax4.set_title("Top Categories (All Time)", color=TEXT_COLOR, fontsize=10, pad=10)
    ax4.set_xlabel("Total Spent (₹)", color=TEXT_COLOR, fontsize=9)

    chart_path = CHART_DIR / f"dashboard_{today.strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(chart_path, dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close()

    print(C["success"] + f"\n  ✔ Chart saved to: {chart_path}")
    print(C["dim"] + "  Open the PNG file to view your financial analytics dashboard.")
    return chart_path

def export_csv():
    section("📤  EXPORT DATA")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, date, description, amount, type, category, note FROM transactions ORDER BY date DESC"
        ).fetchall()

    if not rows:
        print(C["warn"] + "\n  No transactions to export.")
        return

    filename = EXPORT_DIR / f"transactions_{datetime.date.today().isoformat()}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Date", "Description", "Amount", "Type", "Category", "Note"])
        writer.writerows(rows)

    print(C["success"] + f"\n  ✔ Exported {len(rows)} transactions to:\n    {filename}")

def delete_transaction():
    section("🗑️  DELETE TRANSACTION")
    try:
        tid = int(input("  Enter Transaction ID to delete: ").strip())
    except ValueError:
        print(C["error"] + "  ✗ Invalid ID.")
        return
    with get_conn() as conn:
        row = conn.execute("SELECT date, description, amount, type FROM transactions WHERE id=?", (tid,)).fetchone()
        if not row:
            print(C["warn"] + "\n  Transaction not found.")
            return
        print(f"\n  Found: [{row[0]}] {row[1]} — {fmt_amount(row[2], row[3])}")
        confirm = input("  Confirm delete? [y/N]: ").strip().lower()
        if confirm == "y":
            conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
            print(C["success"] + "  ✔ Deleted.")
        else:
            print(C["dim"] + "  Cancelled.")

# ─── Main Menu ────────────────────────────────────────────────────────────────
def main():
    init_db()
    while True:
        clear()
        banner()
        print(f"""  {C['bold']}MAIN MENU{C['reset']}

  {C['bold']}1.{C['reset']} ➕  Add Transaction       {C['dim']}(income or expense){C['reset']}
  {C['bold']}2.{C['reset']} 📋  View Transactions      {C['dim']}(with filters){C['reset']}
  {C['bold']}3.{C['reset']} 📊  Dashboard              {C['dim']}(summary & spending breakdown){C['reset']}
  {C['bold']}4.{C['reset']} 🎯  Manage Budgets         {C['dim']}(set monthly limits & alerts){C['reset']}
  {C['bold']}5.{C['reset']} 🏆  Savings Goals          {C['dim']}(track your targets){C['reset']}
  {C['bold']}6.{C['reset']} 📈  Generate Charts        {C['dim']}(visual analytics PNG){C['reset']}
  {C['bold']}7.{C['reset']} 📤  Export to CSV          {C['dim']}(backup all data){C['reset']}
  {C['bold']}8.{C['reset']} 🗑️   Delete Transaction     {C['dim']}(by ID){C['reset']}
  {C['bold']}9.{C['reset']} ❌  Exit
""")
        choice = input("  Choose option: ").strip()
        clear()
        banner()

        if choice == "1":   add_transaction()
        elif choice == "2": view_transactions()
        elif choice == "3": view_dashboard()
        elif choice == "4": manage_budgets()
        elif choice == "5": manage_goals()
        elif choice == "6": generate_charts()
        elif choice == "7": export_csv()
        elif choice == "8": delete_transaction()
        elif choice == "9":
            print(C["accent"] + "\n  👋 Goodbye! Stay financially fit.\n")
            sys.exit(0)
        else:
            print(C["warn"] + "\n  ⚠ Invalid option.")

        input(C["dim"] + "\n  Press Enter to continue...")

if __name__ == "__main__":
    main()
