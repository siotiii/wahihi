#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACT 102 - FUNDAMENTALS OF PROGRAMMING  |  Interactive Python Learning System
Associate in Computer Technology I

How to run:   python act102.py
Self-test:    python act102.py --selftest

Features
  * 8 lessons across Prelim, Midterms and Finals (every lesson unlocks the next)
  * Each lesson = explanations + live examples + a coding activity that is
    really executed and checked + a quiz (70% to pass)
  * Progress is saved per student in act102_progress.json (next to this file)
  * Finishing every lesson, activity and quiz automatically awards a
    Certificate of Completion (terminal view + printable HTML file)
Only the Python standard library is used.
"""

import hashlib
import html
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import textwrap
import webbrowser
from datetime import date
from itertools import product
from pathlib import Path

# --------------------------------------------------------------------------
#  TERMINAL SETUP
# --------------------------------------------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
if os.name == "nt":
    os.system("")  # enables ANSI colours in the Windows console


class C:
    R = "\033[0m"
    B = "\033[1m"
    HEAD = "\033[1;38;5;75m"
    GOLD = "\033[38;5;220m"
    GOLDB = "\033[1;38;5;220m"
    OK = "\033[38;5;114m"
    BAD = "\033[38;5;203m"
    DIM = "\033[38;5;245m"
    CODE = "\033[38;5;151m"
    PINK = "\033[1;38;5;177m"
    BLUE = "\033[38;5;75m"


ANSI_RE = re.compile(r"\033\[[0-9;]*m")
PASS_PCT = 70


def paint(text, color):
    return f"{color}{text}{C.R}"


def vlen(s):
    return len(ANSI_RE.sub("", s))


def ljust_v(s, width):
    return s + " " * max(0, width - vlen(s))


def center_v(s, width):
    gap = max(0, width - vlen(s))
    left = gap // 2
    return " " * left + s + " " * (gap - left)


def term_width():
    return max(70, min(shutil.get_terminal_size((90, 24)).columns - 2, 96))


def clear():
    print("\033[2J\033[3J\033[H", end="")


class Quit(Exception):
    """Raised on Ctrl+C / Ctrl+D so the program can exit cleanly."""


def ask(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        raise Quit


def pause(msg="Press Enter to continue..."):
    ask("\n  " + paint(msg, C.DIM))


def D(s):
    return textwrap.dedent(s).strip("\n")


# --------------------------------------------------------------------------
#  STORAGE  (per-student progress, saved automatically)
# --------------------------------------------------------------------------
def _data_dir():
    base = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    if os.access(base, os.W_OK):
        return base
    alt = Path.home() / ".act102"
    alt.mkdir(exist_ok=True)
    return alt


DATA_DIR = _data_dir()
PROGRESS_FILE = DATA_DIR / "act102_progress.json"


def load_data():
    try:
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("students"), dict):
            return d
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        try:  # keep a copy of an unreadable file instead of destroying it
            os.replace(PROGRESS_FILE, PROGRESS_FILE.with_suffix(".bak"))
        except OSError:
            pass
    return {"version": 1, "students": {}}


DATA = load_data()


def save_data():
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(DATA, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PROGRESS_FILE)
    except OSError as e:
        print(paint(f"  Warning: could not save progress ({e}).", C.BAD))


def new_student(name):
    return {"name": name, "created": date.today().isoformat(), "lessons": {},
            "adventure_best": None, "certificate": None}


def lesson_state(student, lid):
    st = student["lessons"].setdefault(str(lid), {})
    st.setdefault("sections", [])
    st.setdefault("activity", False)
    st.setdefault("quiz_best", None)
    st.setdefault("quiz_attempts", 0)
    st.setdefault("completed", False)
    st.setdefault("completed_on", None)
    return st


# --------------------------------------------------------------------------
#  SAFE CODE RUNNER  (used by live examples and by the coding activities)
# --------------------------------------------------------------------------
ECHO_PRELUDE = D('''
    import builtins as _b
    _orig_input = _b.input
    def _echo_input(prompt=""):
        v = _orig_input(prompt)
        print(v)
        return v
    _b.input = _echo_input
''') + "\n"


def run_python(code, stdin_text="", timeout=5):
    """Run code in a separate Python process. Returns (stdout, stderr, returncode).
    returncode is None when the program had to be stopped (timeout)."""
    try:
        p = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-c", code],
            input=stdin_text, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
        return p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        return "", "", None
    except OSError as e:
        return "", str(e), 1


def last_error_line(err):
    lines = [ln for ln in err.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else "unknown error"


# --------------------------------------------------------------------------
#  RENDERING HELPERS
# --------------------------------------------------------------------------
def topbar(student, *crumbs):
    w = term_width()
    left = paint(" ACT 102 · LEARN PYTHON", C.GOLDB)
    right = paint(f"{student['name']} ", C.DIM) if student else ""
    print(left + " " * max(1, w - vlen(left) - vlen(right)) + right)
    print(paint("━" * w, C.GOLD))
    if crumbs:
        print(paint("  " + "  ›  ".join(crumbs), C.DIM))


def main_banner():
    w = term_width()
    lines = [paint("ASSOCIATE IN COMPUTER TECHNOLOGY I", C.DIM),
             paint("FUNDAMENTALS OF PROGRAMMING", C.PINK),
             paint("ACT 102  ·  Learn Python", C.GOLD)]
    print(paint("╔" + "═" * (w - 2) + "╗", C.GOLD))
    for ln in lines:
        print(paint("║", C.GOLD) + center_v(ln, w - 2) + paint("║", C.GOLD))
    print(paint("╚" + "═" * (w - 2) + "╝", C.GOLD))


def bar(done, total, width=24):
    filled = int(width * done / total) if total else 0
    return C.OK + "█" * filled + C.DIM + "░" * (width - filled) + C.R


def rule(ch="─", color=C.DIM):
    print(paint(ch * term_width(), color))


def panel(title, lines, color, numbered=False):
    w = term_width() - 4
    print("  " + paint("┌─ " + title + " " + "─" * max(2, w - len(title) - 4), C.DIM))
    for i, ln in enumerate(lines, 1):
        num = paint(f"{i:>2}  ", C.DIM) if numbered else ""
        print("  " + paint("│", C.DIM) + " " + num + color + ln.rstrip() + C.R)
    print("  " + paint("└" + "─" * (w - 1), C.DIM))


def table(headers, rows):
    cols = len(headers)
    widths = [max(vlen(str(r[i])) for r in [headers] + rows) for i in range(cols)]
    head = paint(" │ ", C.DIM).join(paint(ljust_v(h, widths[i]), C.GOLDB)
                                    for i, h in enumerate(headers))
    print("  " + head)
    print("  " + paint("─┼─".join("─" * w_ for w_ in widths), C.DIM))
    for r in rows:
        print("  " + paint(" │ ", C.DIM).join(ljust_v(str(c), widths[i])
                                            for i, c in enumerate(r)))


def tf(value):
    return paint(str(value), C.OK if value is True else C.BAD)


# content block constructors
def H(t): return ("h", t)
def P(t): return ("p", t)
def B(t): return ("b", t)
def OK(t): return ("ok", t)
def BAD(t): return ("bad", t)
def TIP(t): return ("tip", t)
def CODE(s): return ("code", D(s), None)
def DEMO(s, stdin=None): return ("demo", D(s), stdin)
def OUT(s): return ("out", D(s))
def RAW(s): return ("raw", D(s))
def TABLE(h, rows): return ("table", h, rows)
SP = ("sp",)


def render_blocks(blocks):
    inner = term_width() - 6
    for blk in blocks:
        k = blk[0]
        if k == "h":
            print()
            print("  " + paint(blk[1].upper(), C.HEAD))
            print("  " + paint("─" * min(len(blk[1]), inner), C.DIM))
        elif k == "p":
            for ln in textwrap.wrap(blk[1], inner):
                print("  " + ln)
        elif k == "b":
            for ln in textwrap.wrap(blk[1], inner - 2, initial_indent="• ",
                                    subsequent_indent="  "):
                print("   " + ln)
        elif k in ("ok", "bad", "tip"):
            sym, col = {"ok": ("✔", C.OK), "bad": ("✖", C.BAD), "tip": ("★ TIP:", C.GOLD)}[k]
            wrapped = textwrap.wrap(blk[1], inner - 4)
            for i, ln in enumerate(wrapped):
                lead = paint(sym, col) + " " if i == 0 else " " * (len(sym) + 1)
                print("  " + lead + (paint(ln, col) if k != "tip" else ln))
        elif k == "code":
            panel("PYTHON CODE", blk[1].splitlines(), C.CODE, numbered=True)
        elif k == "demo":
            code, stdin = blk[1], blk[2]
            panel("PYTHON CODE", code.splitlines(), C.CODE, numbered=True)
            src = (ECHO_PRELUDE + code) if stdin else code
            out, err, rc = run_python(src, "\n".join(stdin) + "\n" if stdin else "")
            lines = out.rstrip("\n").splitlines()
            if rc != 0:
                lines.append(paint("⚠ " + (last_error_line(err) if rc is not None
                                           else "program stopped (took too long)"), C.BAD))
            panel("OUTPUT (real result)", lines or ["(no output)"], C.OK)
        elif k == "out":
            panel("OUTPUT", blk[1].splitlines(), C.OK)
        elif k == "raw":
            print()
            for ln in blk[1].splitlines():
                print("  " + paint(ln, C.GOLD))
        elif k == "table":
            print()
            table(blk[1], blk[2])
        elif k == "sp":
            print()


def S(title, *blocks):
    return {"title": title, "blocks": list(blocks)}

# ==========================================================================
#  COURSE CONTENT
# ==========================================================================
LESSONS = []
TERMS = [
    {"name": "PRELIM", "lessons": [1, 2, 3, 4]},
    {"name": "MIDTERMS", "lessons": [5, 6]},
    {"name": "FINALS", "lessons": [7, 8]},
]


def add_lesson(title, sections, activity, quiz):
    LESSONS.append({"id": len(LESSONS) + 1, "title": title, "sections": sections,
                    "activity": activity, "quiz": quiz})


def Q(q, opts, ans, why, code=None):
    return {"q": q, "opts": opts, "ans": ans, "why": why, "code": code}


def flow_if():
    """Flowchart for the if statement (built in code so the lines always align)."""
    right = 35  # column of the right-hand connector
    rows = ["         START",
            "           │",
            "           ▼",
            "   ╭───────────────╮",
            "   │  condition ?  │──── False ────╮",
            ]
    for left in ["   ╰───────┬───────╯", "           │ True", "           ▼",
                 "   ╭───────────────╮", "   │ run the block │", "   ╰───────┬───────╯",
                 "           │", "           ▼"]:
        rows.append(left.ljust(right) + "│")
    rows.append("          END ◄" + "─" * (right - 15) + "╯")
    return "\n".join(rows)


# ---- shared tables -------------------------------------------------------
_OPS = [("+", "Addition: adds two values", "5 + 3"),
        ("-", "Subtraction: second from first", "10 - 4"),
        ("*", "Multiplication: multiplies", "7 * 2"),
        ("/", "Division: always a decimal (float)", "15 / 3"),
        ("//", "Floor division: whole number only", "17 // 3"),
        ("%", "Modulus: the remainder", "10 % 3"),
        ("**", "Exponentiation: raise to a power", "2 ** 3")]
OPS_ROWS = [[paint(o, C.GOLDB), d, e, paint(str(eval(e)), C.OK)] for o, d, e in _OPS]

_REL = [("==", "Equal to", "10 == 10"), ("!=", "Not equal to", "10 != 5"),
        (">", "Greater than", "10 > 5"), ("<", "Less than", "10 < 5"),
        (">=", "Greater than or equal to", "10 >= 5"), ("<=", "Less than or equal to", "5 <= 10")]
REL_ROWS = [[paint(o, C.GOLDB), d, e, tf(eval(e))] for o, d, e in _REL]

AND_ROWS = [[tf(a), tf(b), tf(a and b)] for a, b in product([True, False], repeat=2)]
OR_ROWS = [[tf(a), tf(b), tf(a or b)] for a, b in product([True, False], repeat=2)]
NOT_ROWS = [[tf(a), tf(not a)] for a in (True, False)]

# ==========================================================================
#  LESSON 1
# ==========================================================================
add_lesson(
    "Introduction to Programming & Python",
    [
        S("What is Programming?",
          H("What is Programming?"),
          P("Programming is giving instructions to a computer so it can perform tasks. "
            "A computer cannot think for itself - it follows the exact steps (a program) "
            "that a programmer writes."),
          H("What is a Programming Language?"),
          P("A programming language is a special language that computers understand and "
            "use to perform tasks. Each language has unique strengths suited for specific domains."),
          TABLE(["Language", "Key features & primary use"], [
              [paint("Python", C.GOLDB), "Easy to learn and read; great for beginners, data science, AI, automation"],
              [paint("C / C++", C.GOLDB), "High performance; system programming, games, embedded devices"],
              [paint("PHP", C.GOLDB), "Web development; works smoothly with databases and server-side scripting"],
              [paint("Java", C.GOLDB), "Platform independent (write once, run anywhere); enterprise systems, Android apps"],
              [paint("JavaScript", C.GOLDB), "The core language of the web; adds interactivity to websites"],
              [paint("Ruby", C.GOLDB), "Simple and productive; web frameworks like Rails"],
          ])),
        S("What is Python?",
          H("What is Python Programming?"),
          P("Python is a widely-used, high-level, interpreted, general-purpose programming "
            "language created by Guido van Rossum in 1991. Guido is a Dutch software engineer "
            "who designed Python to be simple, readable and easy to learn - while still being "
            "powerful enough for professional software."),
          B("High-level: closer to human language than to machine code."),
          B("Interpreted: your code is run line by line, so you see results immediately."),
          B("General-purpose: it is not limited to one kind of project."),
          H("Why Learn Python?"),
          OK("Simple and easy to learn - great for beginners."),
          OK("Readable syntax - code looks almost like English."),
          OK("Versatile - AI, web, automation, data science, games and scripting."),
          OK("Huge community - lots of support, tutorials and libraries.")),
        S("Tools & Your First Program",
          H("What do you need to start?"),
          P("You write Python in a code editor or IDE (Integrated Development Environment):"),
          B("PyCharm (by JetBrains)"),
          B("VS Code (Visual Studio Code)"),
          B("Jupyter Notebook / JupyterLab"),
          H("Your first program"),
          P("This program has two instructions. Python runs them from top to bottom."),
          DEMO('''
              print("Hello, World!")
              print("Welcome to ACT102 - Fundamentals of Programming")
          '''),
          TIP("Next you will write a program just like this one in the coding activity.")),
    ],
    dict(
        task=["Write a program that prints these two lines exactly:",
              "    Hello, World!",
              "    Welcome to ACT102 - Fundamentals of Programming"],
        hint='Use the print() function twice. Text must be inside quotes: print("...")',
        solution='print("Hello, World!")\nprint("Welcome to ACT102 - Fundamentals of Programming")',
        needs=[(r"print\s*\(", "Use the print() function.")],
        tests=[dict(inp=[], mode="exact",
                    expect=["Hello, World!", "Welcome to ACT102 - Fundamentals of Programming"])],
    ),
    [
        Q("What is programming?",
          ["Giving instructions to a computer so it can perform tasks", "Repairing computer hardware",
           "Designing computer chips", "Typing documents quickly"], 0,
          "Programming means writing instructions that a computer can follow."),
        Q("Who created the Python programming language in 1991?",
          ["James Gosling", "Guido van Rossum", "Bjarne Stroustrup", "Dennis Ritchie"], 1,
          "Guido van Rossum, a Dutch software engineer, created Python in 1991."),
        Q("Which language is the core language of the web, adding interactivity to websites?",
          ["PHP", "Java", "JavaScript", "Ruby"], 2,
          "JavaScript runs in the browser and makes web pages interactive."),
        Q("Which of these is NOT a reason to learn Python?",
          ["Readable syntax that looks almost like English", "A huge community with many libraries",
           "It is used in AI, web and automation", "It can only be used for one type of project"], 3,
          "Python is versatile - it is used in many fields, not just one."),
        Q("Which of these is a Python IDE / code editor mentioned in the lesson?",
          ["Photoshop", "PyCharm", "Excel", "Chrome"], 1,
          "PyCharm (by JetBrains), VS Code and Jupyter are tools for writing Python."),
    ],
)

# ==========================================================================
#  LESSON 2
# ==========================================================================
add_lesson(
    "Python Basic Syntax",
    [
        S("Syntax",
          H("Syntax"),
          P("Syntax refers to the set of rules that tells us how to correctly write a program in Python."),
          H("Example: your first program"),
          DEMO('''
              print("Hello, World!")
              print("Welcome to ACT102 - Fundamentals of Programming")
          '''),
          TIP("Python reads your program from top to bottom, one statement per line.")),
        S("Case-Sensitive",
          H("Python is case-sensitive"),
          P("Python treats uppercase and lowercase letters differently, so name and Name are "
            "two different identifiers."),
          OK("CORRECT - the same spelling is used both times:"),
          DEMO('''
              name = "John"
              print(name)
          '''),
          BAD("INCORRECT - Name is not the same as name:"),
          DEMO('''
              name = "John"
              print(Name)
          ''')),
        S("Indentation",
          H("Indentation"),
          P("Unlike many other languages, Python uses indentation (spaces at the start of a line) "
            "to define blocks of code. The usual size is 4 spaces."),
          OK("CORRECT - the print line is indented, so it is inside the if block:"),
          DEMO('''
              age = 18
              if age >= 18:
                  print("Adult")
          '''),
          BAD("INCORRECT - the print line is not indented:"),
          DEMO('''
              age = 18
              if age >= 18:
              print("Adult")
          ''')),
        S("Printing Output",
          H("1. The print statement"),
          P("The print() function displays information on the screen."),
          CODE("print(value)"),
          B("print - the function that displays output."),
          B("( ) - parentheses that contain the information to display."),
          B("value - the text, number, variable or expression you want to show."),
          H("2. Printing text"),
          P("Text (also called a string) must be enclosed in quotation marks."),
          OK("CORRECT:"),
          DEMO('print("Hello, World!")'),
          BAD("INCORRECT - missing quotes, so Python thinks Hello and World are variable names:"),
          DEMO('print(Hello, World!)'),
          H("3. Printing numbers"),
          P("Numbers are written without quotes. With quotes they become text (strings): "
            "the output looks the same, but the data type is different."),
          DEMO('''
              print(100)
              print("100")
              print(type(100))
              print(type("100"))
          '''),
          TIP("Use quotes for text, not for numbers.")),
        S("Python Comments",
          H("Python comments"),
          B("Comments are ignored by Python."),
          B("They are used to explain the code."),
          H("Single-line comment: #"),
          P("Starts with the hash symbol and continues to the end of the line. Used for short "
            "explanations, quick notes, or disabling a line of code."),
          DEMO('''
              # This is a comment
              print("Hello")  # this note is ignored too
          '''),
          H("Multi-line comment: triple quotes"),
          P("Everything between the opening and closing triple quotes is ignored. Used for longer "
            "explanations and documentation."),
          DEMO('''"""
              This is
              a multi-line
              comment.
              """
              print("Hello")'''.replace("              ", ""))),
        S("Variables & Assigning Values",
          H("What is a variable?"),
          B("A variable is a named storage location used to keep data in a program."),
          B("The value of a variable can change while the program is running."),
          RAW('''
              ┌───────────┐     ┌───────────┐
              │    age    │     │   name    │   ← variable name
              ├───────────┤     ├───────────┤
              │    20     │     │  "John"   │   ← stored value
              └───────────┘     └───────────┘
          '''),
          H("Assigning a value"),
          P("We assign a value to a variable using the = (assignment operator). The variable name "
            "goes on the left, the value on the right."),
          DEMO('''
              first_name = "John"
              age = 20
              print(first_name)
              print(age)
          '''),
          H("Changing a value"),
          DEMO('''
              score = 10
              score = 25
              print(score)
          ''')),
        S("Variable Naming Rules",
          H("Rules for naming variables"),
          B("Must start with a letter or the underscore character (_)."),
          B("Cannot start with a number."),
          B("Can only contain letters, numbers and underscores (no spaces or symbols like @ # $ % .)."),
          B("Are case-sensitive: age and AGE are different variables."),
          TABLE([paint("✔ VALID", C.OK), paint("✖ INVALID", C.BAD), "Why it is invalid"], [
              [paint("age", C.OK), paint("1stValue", C.BAD), "starts with a number"],
              [paint("_value", C.OK), paint("#bread", C.BAD), "special character #"],
              [paint("total", C.OK), paint("var.12", C.BAD), "special character ."],
              [paint("spam23", C.OK), paint("space name", C.BAD), "contains a space"],
              [paint("NUMBER", C.OK), paint("@value", C.BAD), "special character @"],
          ]),
          H("Short vs descriptive names"),
          P("Both are valid. Use short names (x, y, i, n) for quick temporary values and descriptive "
            "names (age, carname, total_volume) when your code grows or is read by others."),
          H("Case-sensitive in action"),
          DEMO('''
              number = 10
              Number = 20
              NUMBER = 30
              print(number, Number, NUMBER)
          '''),
          P("These are three different variables.")),
        S("Output Variables & Constants",
          H("Output several variables with a comma"),
          DEMO('''
              a = "I"
              b = "LOVE"
              c = "CCST"
              print(a, b, c)
          '''),
          P("The comma prints each value separated by a space."),
          H("Join strings with +"),
          DEMO('''
              x = "I "
              y = "LOVE "
              z = "CCST"
              print(x + y + z)
          '''),
          P("The + operator joins (concatenates) the strings exactly as they are, in order. "
            "That is why the spaces were typed inside the quotes."),
          H("Constants"),
          P("Python has no true constants. By convention, a value that should never change is "
            "written in UPPERCASE."),
          DEMO('''
              PI = 3.14159
              SCHOOL = "Clark College"
              print(PI, SCHOOL)
          ''')),
        S("Basic Data Types",
          H("Data types"),
          P("Data types are categories that tell Python what kind of data a variable stores, and "
            "what operations can be performed on it."),
          TABLE(["Type", "Description", "Examples"], [
              [paint("int", C.GOLDB), "Whole numbers (no decimal part)", "10, 25, -7, 100"],
              [paint("float", C.GOLDB), "Numbers with a decimal point", "12.5, 3.14, -0.001, 2.0"],
              [paint("str", C.GOLDB), "Text inside quotes", '"Hello", "Juan", "CCST"'],
              [paint("bool", C.GOLDB), "One of two values: True or False", "True, False"],
          ]),
          H("Declaring variables and checking their type"),
          DEMO('''
              name = "Maria"
              age = 20
              grade = 89.5
              is_enrolled = True
              print(name, type(name))
              print(age, type(age))
              print(grade, type(grade))
              print(is_enrolled, type(is_enrolled))
          '''),
          TIP("Choosing the right type helps your program work correctly.")),
    ],
    dict(
        task=["Create four variables, then print each one on its own line (in this order):",
              "    name        = the text Maria",
              "    age         = the whole number 20",
              "    grade       = the decimal number 89.5",
              "    is_enrolled = True",
              "Expected output:  Maria / 20 / 89.5 / True (one per line)"],
        hint='name = "Maria"   (text needs quotes)  -  age = 20  -  then print(name), print(age) ...',
        solution='name = "Maria"\nage = 20\ngrade = 89.5\nis_enrolled = True\n'
                 'print(name)\nprint(age)\nprint(grade)\nprint(is_enrolled)',
        needs=[(r"\bname\s*=", "Create a variable named name."),
               (r"\bage\s*=", "Create a variable named age."),
               (r"\bgrade\s*=", "Create a variable named grade."),
               (r"\bis_enrolled\s*=", "Create a variable named is_enrolled.")],
        tests=[dict(inp=[], mode="exact", expect=["Maria", "20", "89.5", "True"])],
    ),
    [
        Q("In Python, which statement is true about name and Name?",
          ["They are two different identifiers", "They are the same variable",
           "Name causes a SyntaxError", "Python ignores uppercase letters"], 0,
          "Python is case-sensitive, so uppercase and lowercase letters are different."),
        Q("Which of these is a valid variable name?",
          ["1st_value", "my-name", "_speed", "student name"], 2,
          "A name may start with a letter or underscore; it cannot start with a number, "
          "contain a hyphen or contain spaces."),
        Q("How does Python define blocks of code, such as the inside of an if statement?",
          ["Curly braces { }", "Indentation", "Semicolons", "Parentheses"], 1,
          "Python uses indentation instead of braces."),
        Q("How do you write a single-line comment in Python?",
          ["// This is a comment", "# This is a comment", "/* This is a comment */", "-- This is a comment"], 1,
          "A comment starts with the hash symbol #."),
        Q("What does this code print?", ["<class 'int'>", "<class 'str'>", "<class 'float'>", "100"], 1,
          'Anything inside quotes is a string, even if it looks like a number.',
          code='print(type("100"))'),
    ],
)

# ==========================================================================
#  LESSON 3
# ==========================================================================
add_lesson(
    "Arithmetic Operators and Expressions",
    [
        S("Arithmetic Operators",
          H("What are arithmetic operators?"),
          P("Arithmetic operators are symbols used to perform mathematical calculations on numbers. "
            "They work the same way as the operators in everyday mathematics."),
          TABLE(["Operator", "Description", "Example", "Result"], OPS_ROWS),
          TIP("/ always gives a decimal (15 / 3 is 5.0). // gives only the whole number part.")),
        S("Expressions",
          H("Expressions in Python"),
          P("An expression is a combination of values, variables and operators that evaluates to a result."),
          H("Example: add two numbers"),
          DEMO('''
              a = 10
              b = 5
              result = a + b
              print("The result is:", result)
          '''),
          H("All the operators (a = 10, b = 5)"),
          DEMO('''
              a = 10
              b = 5
              print("Addition:", a + b)
              print("Subtraction:", a - b)
              print("Multiplication:", a * b)
              print("Division:", a / b)
              print("Floor Division:", a // b)
              print("Modulus:", a % b)
              print("Exponentiation:", a ** b)
          ''')),
        S("Order of Operations (PEMDAS)",
          H("PEMDAS"),
          P("Python follows the order of operations. Operators on the same level are solved "
            "from left to right."),
          TABLE(["Order", "Letter", "Operation"], [
              ["1st", "P", "Parentheses ( )"],
              ["2nd", "E", "Exponents **"],
              ["3rd", "M / D", "Multiplication and Division (left to right)"],
              ["4th", "A / S", "Addition and Subtraction (left to right)"],
          ]),
          H("Try it"),
          DEMO('''
              a = 2
              b = 3
              c = 4
              print(a + b * c)
              print((a + b) * c)
              print(20 / 4 * 2)
          '''),
          P("a + b * c is 14 because multiplication happens first: 3 * 4 = 12, then 2 + 12. "
            "With parentheses, (a + b) * c is 5 * 4 = 20.")),
        S("Handy Tricks: // and %",
          H("Floor division and modulus"),
          P("// tells you how many times a number fits inside another, and % gives what is left over."),
          DEMO('''
              print(17 // 3)
              print(17 % 3)
          '''),
          P("17 = 3 x 5 + 2, so 17 // 3 is 5 and 17 % 3 is 2."),
          H("Is a number even or odd?"),
          P("An even number has a remainder of 0 when divided by 2."),
          DEMO('''
              n = 7
              print(n % 2 == 0)
          ''')),
    ],
    dict(
        task=["Store a = 17 and b = 5. Then print these seven results,",
              "each on its own line and in this order:",
              "    a + b,  a - b,  a * b,  a / b,  a // b,  a % b,  a ** b"],
        hint="a = 17, b = 5, then print(a + b), print(a - b), print(a * b), ...",
        solution="a = 17\nb = 5\nprint(a + b)\nprint(a - b)\nprint(a * b)\nprint(a / b)\n"
                 "print(a // b)\nprint(a % b)\nprint(a ** b)",
        needs=[(r"\ba\s*=\s*17", "Create a variable a = 17."),
               (r"\bb\s*=\s*5", "Create a variable b = 5.")],
        tests=[dict(inp=[], mode="exact",
                    expect=["22", "12", "85", "3.4", "3", "2", "1419857"])],
    ),
    [
        Q("What is the result of 17 // 3?", ["5", "5.67", "2", "6"], 0,
          "// is floor division: it keeps only the whole number part, so 17 // 3 = 5."),
        Q("What is the result of 10 % 3?", ["3", "1", "0", "3.33"], 1,
          "% returns the remainder: 10 = 3 x 3 + 1."),
        Q("What is printed?", ["20", "14", "ERROR", "9"], 1,
          "Multiplication comes first: 3 * 4 = 12, then 2 + 12 = 14.",
          code="a = 2\nb = 3\nc = 4\nprint(a + b * c)"),
        Q("What is 2 ** 3?", ["6", "8", "9", "23"], 1, "** raises to a power: 2 x 2 x 2 = 8."),
        Q("What does 15 / 3 give in Python?", ["5", "5.0", "3", "45"], 1,
          "The / operator always returns a decimal (float) result."),
    ],
)

# ==========================================================================
#  LESSON 4
# ==========================================================================
add_lesson(
    "Basic Input and Output in Python",
    [
        S("Accepting User Input",
          H("Why do we need input?"),
          P("Input lets a program respond to the user instead of always doing the same thing - "
            "just like asking someone for their name and then greeting them."),
          H("The input() function"),
          CODE('variable = input("Prompt message: ")'),
          B("The text inside the quotes is shown to the user."),
          B("Whatever the user types is stored in the variable."),
          B("All input is a string (str) by default."),
          DEMO('''
              name = input("Enter your name: ")
              print("Hello,", name)
          ''', stdin=["Maria"]),
          TIP("In the demo above, the typed answer was Maria.")),
        S("Formatting Output",
          H("Using a comma in print()"),
          DEMO('''
              name = input("Enter your name: ")
              age = input("Enter your age: ")
              print("Name:", name)
              print("Age:", age)
          ''', stdin=["Maria", "20"]),
          H("Using an f-string"),
          P("Put the letter f before the quotes, then place variables inside { }."),
          DEMO('''
              name = "Maria"
              age = 20
              print(f"{name} is {age} years old.")
          ''')),
        S("Converting Input",
          H("Input is always text"),
          P("Even when the user types 20, Python stores it as the string '20'. "
            "That is a problem for math:"),
          DEMO('''
              age = input("Age: ")
              print(age + 1)
          ''', stdin=["20"]),
          H("Type conversion"),
          B("int(...)   - whole numbers"),
          B("float(...) - decimal numbers"),
          B("Boolean input - compare the text, for example answer.lower() == \"yes\""),
          DEMO('''
              age = int(input("Age: "))
              grade = float(input("Grade: "))
              answer = input("Are you a student? (yes/no): ")
              is_student = answer.lower() == "yes"
              print(age + 1, grade + 1, is_student)
          ''', stdin=["20", "89.5", "YES"])),
        S("Putting It All Together",
          H("Example program (combining everything)"),
          DEMO('''
              name = input("Enter your name: ")
              age = int(input("Enter your age: "))
              grade = float(input("Enter your final grade: "))
              print(f"Student: {name}, Age: {age}, Final Grade: {grade}")
          ''', stdin=["Maria", "20", "89.5"]),
          TIP("The coding activity asks you to write this program yourself.")),
    ],
    dict(
        task=["Write a program that asks for a student's name (text), age (whole number) and",
              "final grade (decimal) using input(), then prints exactly this format:",
              "    Student: Maria, Age: 20, Final Grade: 89.5"],
        hint='Use int(input(...)) for age and float(input(...)) for grade, then an f-string: '
             'print(f"Student: {name}, Age: {age}, Final Grade: {grade}")',
        solution='name = input("Enter your name: ")\nage = int(input("Enter your age: "))\n'
                 'grade = float(input("Enter your final grade: "))\n'
                 'print(f"Student: {name}, Age: {age}, Final Grade: {grade}")',
        needs=[(r"input\s*\(", "Use the input() function."),
               (r"int\s*\(", "Convert the age with int()."),
               (r"float\s*\(", "Convert the grade with float().")],
        tests=[dict(inp=["Maria", "20", "89.5"], mode="last",
                    expect="Student: Maria, Age: 20, Final Grade: 89.5"),
               dict(inp=["Juan", "19", "91"], mode="last",
                    expect="Student: Juan, Age: 19, Final Grade: 91.0")],
    ),
    [
        Q("What data type does input() return by default?", ["int", "float", "str", "bool"], 2,
          "input() always returns a string, even if the user types digits."),
        Q("Which line correctly reads a whole number from the user?",
          ["age = input(int)", "age = int(input('Age: '))", "age = integer(input('Age: '))",
           "age = input('Age: ').int()"], 1,
          "Wrap input() inside int() to convert the typed text into a whole number."),
        Q("Which function converts input into a decimal number?", ["str()", "float()", "bool()", "int()"], 1,
          "float() converts text such as '89.5' into a decimal number."),
        Q("What does this code print?", ["Name: Maria", "Name:Maria", "Name: name", "Maria"], 0,
          "A comma in print() separates the values with a space.",
          code='name = "Maria"\nprint("Name:", name)'),
        Q("What does this code print?", ["yes", "True", "False", "YES"], 1,
          "answer.lower() becomes 'yes', and 'yes' == 'yes' is True.",
          code='answer = "YES"\nis_student = answer.lower() == "yes"\nprint(is_student)'),
    ],
)

# ==========================================================================
#  LESSON 5  (MIDTERMS)
# ==========================================================================
add_lesson(
    "Conditional Statements in Python",
    [
        S("Introduction to Conditional Statements",
          H("Introduction to conditional statements"),
          P("A conditional statement allows a program to make decisions based on whether a "
            "condition is True or False."),
          H("Basic structure"),
          CODE('''
              if condition:
                  statement
          '''),
          B("if - the keyword that starts the conditional statement."),
          B("condition - evaluated by Python. If it is True, the indented statement is executed."),
          B("statement - the code that runs only when the condition is True."),
          H("Example"),
          DEMO('''
              age = 18
              if age >= 18:
                  print("You are an adult.")
          '''),
          TIP("In simple terms: the program checks the condition. If True, it does something. "
              "If False, it does nothing (or something else).")),
        S("Relational Operators",
          H("Relational (comparison) operators"),
          P("Relational operators compare two values. The result is always True or False."),
          TABLE(["Operator", "Meaning", "Example", "Result"], REL_ROWS),
          H("Example"),
          DEMO('''
              score = 85
              print(score >= 75)
          '''),
          P("Since 85 is greater than or equal to 75, the expression score >= 75 is True."),
          TIP("= assigns a value, == compares two values. Writing if age = 18: is an error.")),
        S("The if Statement",
          H("The if statement"),
          P("The if statement executes a block of code only when its condition is True."),
          CODE('''
              if condition:
                  statement(s)
          '''),
          B("If the condition is True, the indented block runs."),
          B("If the condition is False, the block is skipped."),
          H("How it works"),
          RAW(flow_if()),
          H("Example 1: condition is True"),
          DEMO('''
              age = 20
              if age >= 18:
                  print("You are an adult.")
          '''),
          H("Example 2: condition is False - nothing is printed inside the block"),
          DEMO('''
              age = 15
              if age >= 18:
                  print("You are an adult.")
              print("Program finished.")
          '''),
          TIP("The block of code must be indented, and it runs only when the condition is True.")),
        S("The if-else Statement",
          H("The if-else statement"),
          P("else provides an alternative when the if condition is False. "
            "Only one of the two blocks is ever executed."),
          CODE('''
              if condition:
                  statement
              else:
                  statement
          '''),
          H("Example 1"),
          DEMO('''
              score = 65
              if score >= 75:
                  print("PASSED")
              else:
                  print("FAILED")
          '''),
          P("score is 65, which is less than 75, so the else block runs."),
          H("Example 2: using == and !="),
          DEMO('''
              password = "python123"
              entered = "python123"
              if entered == password:
                  print("Access granted")
              else:
                  print("Access denied")
          ''')),
        S("The if-elif-else Statement",
          H("The if-elif-else statement"),
          P("Use elif (else if) when there are more than two possible outcomes. Python checks "
            "the conditions from top to bottom and runs the first one that is True; the rest are skipped."),
          CODE('''
              if condition1:
                  statement
              elif condition2:
                  statement
              else:
                  statement
          '''),
          H("Example: grading"),
          DEMO('''
              score = int(input("Enter score: "))
              if score >= 90:
                  print("Grade: Excellent")
              elif score >= 75:
                  print("Grade: Passed")
              else:
                  print("Grade: Failed")
          ''', stdin=["85"]),
          P("85 is not >= 90, so Python moves on to elif. 85 >= 75 is True, so it prints "
            "Grade: Passed and skips the else block.")),
        S("Nested Conditions",
          H("Nested conditions"),
          P("A nested condition is an if statement placed inside another if statement. "
            "The inner decision is only made when the outer condition is True."),
          DEMO('''
              age = 20
              has_id = True
              if age >= 18:
                  if has_id:
                      print("Entry allowed")
                  else:
                      print("Please show your ID")
              else:
                  print("Too young to enter")
          '''),
          P("Each level of nesting needs its own extra indentation. Change age to 15 or has_id to "
            "False in your head and trace which message appears."),
          TIP("In the next lesson you will learn logical operators, which often replace nesting.")),
    ],
    dict(
        task=["Write a program that reads a score with int(input()) and prints ONE of:",
              "    Grade: Excellent   (score is 90 or higher)",
              "    Grade: Passed      (75 to 89)",
              "    Grade: Failed      (below 75)",
              "Use if, elif and else."],
        hint="if score >= 90: ...   elif score >= 75: ...   else: ...   (remember the colons and indentation)",
        solution='score = int(input("Enter score: "))\nif score >= 90:\n    print("Grade: Excellent")\n'
                 'elif score >= 75:\n    print("Grade: Passed")\nelse:\n    print("Grade: Failed")',
        needs=[(r"\bif\b", "Use an if statement."), (r"\belif\b", "Use an elif statement."),
               (r"\belse\b", "Use an else statement.")],
        tests=[dict(inp=[s], mode="last", expect=e) for s, e in [
            ("95", "Grade: Excellent"), ("90", "Grade: Excellent"), ("89", "Grade: Passed"),
            ("75", "Grade: Passed"), ("74", "Grade: Failed"), ("0", "Grade: Failed")]],
    ),
    [
        Q("Which operator checks whether two values are equal?", ["=", "==", "!=", "=>"], 1,
          "== compares values. A single = assigns a value to a variable."),
        Q("What does this code print?", ["True", "False", "85", "Error"], 0,
          "85 is greater than or equal to 75, so the comparison is True.",
          code="score = 85\nprint(score >= 75)"),
        Q("In an if-else statement, how many of the blocks are executed?",
          ["Both blocks", "Only one block", "Neither block", "It depends on the variable name"], 1,
          "Only one of the if or else blocks runs - never both."),
        Q("What does this code print?", ["A", "B", "C", "A and B"], 1,
          "80 is not >= 90, but it is >= 75, so the elif block runs and the rest is skipped.",
          code='score = 80\nif score >= 90:\n    print("A")\nelif score >= 75:\n    print("B")\nelse:\n    print("C")'),
        Q("What must be done to the statements that belong inside an if block?",
          ["Write them in uppercase", "Indent them", "Put them in quotes", "End them with a semicolon"], 1,
          "Python uses indentation to know which statements belong to the if block."),
    ],
)

# ==========================================================================
#  LESSON 6  (MIDTERMS)
# ==========================================================================
add_lesson(
    "Logical Operators",
    [
        S("Introduction to Logical Operators",
          H("What are logical operators?"),
          P("Logical operators combine or reverse conditions. They let one if statement check "
            "several things at once."),
          TABLE(["Operator", "Rule", "Memory aid"], [
              [paint("and", C.GOLDB), "True only if ALL conditions are True", '"Kailangan lahat True"'],
              [paint("or", C.GOLDB), "True if AT LEAST ONE condition is True", '"Kahit isa lang True"'],
              [paint("not", C.GOLDB), "Reverses the result (True becomes False)", '"Baliktarin ang result"'],
          ])),
        S("The and Operator",
          H("and - all conditions must be True"),
          TABLE(["A", "B", "A and B"], AND_ROWS),
          H("Example"),
          DEMO('''
              age = 25
              has_id = True
              if age >= 18 and has_id:
                  print("Entry allowed")
              else:
                  print("Entry denied")
          '''),
          P("Both age >= 18 and has_id are True, so the whole condition is True. "
            "If either one were False, the else block would run.")),
        S("The or Operator",
          H("or - at least one condition must be True"),
          TABLE(["A", "B", "A or B"], OR_ROWS),
          H("Example"),
          DEMO('''
              day = "Sunday"
              if day == "Saturday" or day == "Sunday":
                  print("It is the weekend!")
              else:
                  print("It is a weekday.")
          '''),
          P("Only the second condition is True, which is enough for or.")),
        S("The not Operator",
          H("not - reverses the result"),
          TABLE(["A", "not A"], NOT_ROWS),
          H("Example"),
          DEMO('''
              is_raining = False
              if not is_raining:
                  print("Let's play outside!")
              else:
                  print("Stay inside.")
          '''),
          P("is_raining is False, and not False is True, so the first block runs.")),
        S("Combining Operators",
          H("Order of evaluation"),
          P("When you mix logical operators Python evaluates not first, then and, then or. "
            "Use parentheses to make your intention clear."),
          DEMO('''
              print(True or False and False)
              print((True or False) and False)
              print(not True or True)
          '''),
          H("Combining with relational operators"),
          DEMO('''
              age = 25
              print(age >= 18 and age <= 59)
              print(18 <= age <= 59)
              print(age < 0 or age > 100)
          '''),
          TIP("Python also allows chained comparisons such as 18 <= age <= 59.")),
        S("Putting It All Together",
          H("Age category program"),
          P("This program combines if-elif-else with the or operator to reject invalid ages "
            "before it classifies valid ones."),
          DEMO('''
              age = int(input("Enter age: "))
              if age < 0 or age > 100:
                  print("Invalid input")
              elif age <= 12:
                  print("Category: Child")
              elif age <= 19:
                  print("Category: Teenager")
              elif age <= 59:
                  print("Category: Adult")
              else:
                  print("Category: Senior Citizen")
          ''', stdin=["15"]),
          P("15 is a valid age, not <= 12, but <= 19, so the category is Teenager."),
          TIP("The coding activity asks you to write this program yourself.")),
    ],
    dict(
        task=["Write a program that reads an age with int(input()) and prints ONE of:",
              "    Invalid input         (age below 0 or above 100)  - use the or operator",
              "    Category: Child       (0 to 12)",
              "    Category: Teenager    (13 to 19)",
              "    Category: Adult       (20 to 59)",
              "    Category: Senior Citizen   (60 to 100)"],
        hint="First check: if age < 0 or age > 100: ...  then elif age <= 12 ... elif age <= 19 ... elif age <= 59 ... else ...",
        solution='age = int(input("Enter age: "))\nif age < 0 or age > 100:\n    print("Invalid input")\n'
                 'elif age <= 12:\n    print("Category: Child")\nelif age <= 19:\n    print("Category: Teenager")\n'
                 'elif age <= 59:\n    print("Category: Adult")\nelse:\n    print("Category: Senior Citizen")',
        needs=[(r"\bor\b", "Use the or operator for the invalid-age check."),
               (r"\belif\b", "Use elif for the categories.")],
        tests=[dict(inp=[a], mode="last", expect=e) for a, e in [
            ("-5", "Invalid input"), ("101", "Invalid input"), ("0", "Category: Child"),
            ("12", "Category: Child"), ("13", "Category: Teenager"), ("19", "Category: Teenager"),
            ("20", "Category: Adult"), ("59", "Category: Adult"), ("60", "Category: Senior Citizen"),
            ("100", "Category: Senior Citizen")]],
    ),
    [
        Q("What does this code print?", ["True", "False", "None", "Error"], 1,
          "and is True only when ALL conditions are True; here one is False.",
          code="print(True and False)"),
        Q("What does this code print?", ["True", "False", "None", "Error"], 0,
          "or is True when AT LEAST ONE condition is True.",
          code="print(False or True)"),
        Q("What does this code print?", ["True", "False", "None", "Error"], 1,
          "not reverses the result: not True is False.",
          code="print(not True)"),
        Q('Which operator matches the memory aid "Kailangan lahat True"?', ["and", "or", "not", "=="], 0,
          "and needs ALL conditions to be True."),
        Q("What does this code print?", ["True", "False", "25", "Error"], 0,
          "25 >= 18 is True and 25 <= 59 is True, so True and True is True.",
          code="age = 25\nprint(age >= 18 and age <= 59)"),
    ],
)

# ==========================================================================
#  LESSON 7  (FINALS)
# ==========================================================================
add_lesson(
    "Iteration: The for Loop and range()",
    [
        S("What is Iteration?",
          H("Iteration"),
          P("Iteration is the process of repeatedly executing a block of statements. "
            "Instead of writing the same line many times, we write a loop."),
          TABLE(["Loop", "Type", "Use it when..."], [
              [paint("for", C.GOLDB), "Definite iteration", "you know how many times to repeat"],
              [paint("while", C.GOLDB), "Indefinite (conditional) iteration", "you repeat until a condition changes"],
          ]),
          H("Without a loop vs with a loop"),
          DEMO('''
              print("Hello")
              print("Hello")
              print("Hello")
          '''),
          DEMO('''
              for i in range(3):
                  print("Hello")
          ''')),
        S("The for Loop and range()",
          H("for loop with range()"),
          CODE('''
              for variable in range(start, stop, step):
                  statement
          '''),
          B("start - first value (default 0)."),
          B("stop - the loop stops BEFORE this value; it is never included."),
          B("step - how much to add each time (default 1)."),
          DEMO('''
              for num in range(1, 6):
                  print(num)
          '''),
          P("range(1, 6) produces 1, 2, 3, 4, 5 - the stop value 6 is not included."),
          TABLE(["Call", "Values produced"], [
              ["range(5)", ", ".join(map(str, range(5)))],
              ["range(1, 6)", ", ".join(map(str, range(1, 6)))],
              ["range(1, 10, 2)", ", ".join(map(str, range(1, 10, 2)))],
              ["range(5, 0, -1)", ", ".join(map(str, range(5, 0, -1)))],
          ])),
        S("Step and Countdown",
          H("Counting by a step"),
          P("Print the odd numbers from 1 to 9 by using a step of 2:"),
          DEMO('''
              for num in range(1, 10, 2):
                  print(num)
          '''),
          H("Counting down"),
          P("Use a negative step to count backwards. Start high, stop below the last number you want:"),
          DEMO('''
              for num in range(5, 0, -1):
                  print(num)
          ''')),
        S("Accumulating and Looping Over Text",
          H("Running total (accumulator)"),
          DEMO('''
              total = 0
              for n in range(1, 11):
                  total += n
              print("Sum of 1 to 10:", total)
          '''),
          P("total += n is a shortcut for total = total + n."),
          H("Looping over the letters of a string"),
          DEMO('''
              for letter in "Python":
                  print(letter, end=" ")
              print()
          ''')),
        S("Nested for Loops (Bonus)",
          H("A loop inside a loop"),
          P("The inner loop runs completely for every single pass of the outer loop."),
          DEMO('''
              for i in range(1, 4):
                  for j in range(1, 4):
                      print(i * j, end=" ")
                  print()
          '''),
          P("This prints a 3 x 3 multiplication table. The empty print() moves to a new line "
            "after each row.")),
    ],
    dict(
        task=["Use for loops with range() to print on separate lines:",
              "    first the numbers 1 to 5,",
              "    then a countdown from 5 to 1.",
              "Expected output:  1 2 3 4 5 5 4 3 2 1  (one number per line)"],
        hint="for num in range(1, 6): print(num)   then   for num in range(5, 0, -1): print(num)",
        solution="for num in range(1, 6):\n    print(num)\nfor num in range(5, 0, -1):\n    print(num)",
        needs=[(r"\bfor\b", "Use a for loop."), (r"range\s*\(", "Use the range() function.")],
        tests=[dict(inp=[], mode="exact", expect=["1", "2", "3", "4", "5", "5", "4", "3", "2", "1"])],
    ),
    [
        Q("What does this code print?",
          ["1, 2, 3, 4, 5 (one per line)", "1, 2, 3, 4, 5, 6", "0, 1, 2, 3, 4, 5", "2, 3, 4, 5"], 0,
          "range(1, 6) starts at 1 and stops BEFORE 6.",
          code="for num in range(1, 6):\n    print(num)"),
        Q("Which values does range(1, 10, 2) produce?",
          ["1, 3, 5, 7, 9", "2, 4, 6, 8", "1, 2, 3, ... 10", "1, 3, 5, 7, 9, 11"], 0,
          "It starts at 1, adds 2 each time, and stops before 10."),
        Q("Which call produces a countdown from 5 to 1?",
          ["range(5, 0, -1)", "range(1, 5, -1)", "range(5, 1)", "range(5, 0)"], 0,
          "A negative step counts down; the stop value 0 is excluded, so the last number is 1."),
        Q("When is a for loop the best choice?",
          ["When the number of repetitions is known in advance",
           "When repeating until the user types a stop value",
           "When you want to compare two numbers", "When you want to avoid using variables"], 0,
          "for loops are for definite iteration - a known number of repetitions."),
        Q("How many times does this loop repeat?", ["2", "3", "4", "Forever"], 1,
          "range(3) produces 0, 1, 2 - that is three repetitions.",
          code="for i in range(3):\n    print(i)"),
    ],
)

# ==========================================================================
#  LESSON 8  (FINALS)
# ==========================================================================
add_lesson(
    "Iteration: The while Loop & Sentinel Control",
    [
        S("The while Loop",
          H("The while loop"),
          P("A while loop repeats its statements as long as its condition remains True."),
          CODE('''
              while condition:
                  statement(s)
          '''),
          RAW('''
              1. Check the condition
              2. True  -> run the loop body, then go back to step 1
              3. False -> skip the body and continue after the loop
          '''),
          H("Example: count from 1 to 5"),
          DEMO('''
              count = 1
              while count <= 5:
                  print(count)
                  count += 1
          '''),
          BAD("Careful: if the condition never becomes False (for example you forget count += 1), "
              "the loop runs forever. This is called an infinite loop.")),
        S("while True and Sentinel Control",
          H("while True with break"),
          P("Using while True creates a loop that runs until an explicit break statement is hit. "
            "The special value that tells the loop to stop (such as 0) is called a sentinel value."),
          H("Seatwork: running total until 0 is entered"),
          DEMO('''
              total = 0
              while True:
                  num = int(input("Enter an integer (0 to stop): "))
                  if num == 0:
                      break
                  total += num
              print(f"Total: {total}")
          ''', stdin=["5", "10", "0"]),
          B("The loop keeps asking for numbers."),
          B("total += num adds each number to the running total."),
          B("When the user types the sentinel 0, break ends the loop immediately.")),
        S("break and continue",
          H("break and continue"),
          B("break - exits the loop completely."),
          B("continue - skips the rest of this pass and jumps to the next repetition."),
          DEMO('''
              n = 0
              while True:
                  n += 1
                  if n == 3:
                      continue
                  if n > 5:
                      break
                  print(n)
          '''),
          P("3 is skipped by continue, and the loop ends when n becomes 6.")),
        S("Choosing a Loop & Recap",
          H("for or while?"),
          TABLE(["Use a for loop when...", "Use a while loop when..."], [
              ["you know the number of repetitions", "you do not know how many repetitions"],
              ["looping over range() or a string", "waiting for a condition or sentinel value"],
              ["example: print 1 to 5", "example: keep asking until the user types 0"],
          ]),
          H("Recap"),
          OK("for + range(start, stop, step) = definite iteration."),
          OK("while condition = repeat while the condition stays True."),
          OK("while True + break = loop until a sentinel value is entered."),
          OK("continue skips to the next repetition."),
          TIP("The menus in this learning system use while True loops with break - "
              "you have been using one the whole time.")),
    ],
    dict(
        task=["Write the seatwork program: keep asking for integers with",
              '    int(input("Enter an integer (0 to stop): "))',
              "and add them to a running total. When the user enters 0, stop the loop",
              "and print the result in this format:",
              "    Total: 15"],
        hint="total = 0, then  while True:  read num; if num == 0: break; otherwise total += num. "
             "After the loop: print(f\"Total: {total}\")",
        solution='total = 0\nwhile True:\n    num = int(input("Enter an integer (0 to stop): "))\n'
                 '    if num == 0:\n        break\n    total += num\nprint(f"Total: {total}")',
        needs=[(r"\bwhile\b", "Use a while loop."), (r"\bbreak\b", "Use break to stop at the sentinel."),
               (r"input\s*\(", "Use input() to read each number.")],
        tests=[dict(inp=i, mode="last", expect=e) for i, e in [
            (["5", "10", "0"], "Total: 15"), (["0"], "Total: 0"),
            (["3", "-1", "4", "0"], "Total: 6"), (["100", "200", "300", "0"], "Total: 600")]],
    ),
    [
        Q("A while loop repeats its statements...",
          ["exactly 10 times", "as long as its condition remains True", "only once", "until a for loop ends"], 1,
          "while is conditional iteration: it repeats while the condition is True."),
        Q("Which statement exits a while True loop?", ["stop", "break", "continue", "pass"], 1,
          "break ends the loop immediately."),
        Q("What is a sentinel value?",
          ["A special value that signals the loop to stop (for example 0)", "A kind of variable name",
           "A type of loop", "An error message"], 0,
          "The sentinel is the value that tells the loop it is time to stop."),
        Q("total += num is the same as...",
          ["total = num", "total = total + num", "total = total - num", "total == total + num"], 1,
          "+= adds the value on the right to the variable and stores the result back in it."),
        Q("What does continue do inside a loop?",
          ["Ends the loop", "Skips the rest of this pass and goes to the next repetition",
           "Restarts the whole program", "Prints the loop variable"], 1,
          "continue jumps straight to the next repetition of the loop."),
    ],
)

# ==========================================================================
#  ADVENTURE MODE  (original 10-question Prelim review, kept and fixed)
# ==========================================================================
ADVENTURE = [
    Q("Who created the Python programming language?",
      ["James Gosling", "Guido van Rossum", "Bjarne Stroustrup", "Dennis Ritchie"], 1,
      "Guido van Rossum created Python in 1991."),
    Q("Which of the following is a valid variable name?",
      ["1st_name", "student-name", "student_name", "student name"], 2,
      "Only letters, numbers and underscores are allowed, and it cannot start with a number."),
    Q("What will be the output of this code?", ["3.33", "3", "1", "10"], 1,
      "// is floor division, so 10 // 3 = 3.", code="print(10 // 3)"),
    Q("Python is a ______ language.",
      ["case-insensitive", "case-sensitive", "both a and b", "none of the above"], 1,
      "Python treats name and Name as different identifiers."),
    Q("Which operator is used for exponentiation in Python?", ["^", "**", "*", "//"], 1,
      "** raises a number to a power, e.g. 2 ** 3 = 8."),
    Q("What is the data type of the value True?", ["int", "str", "bool", "float"], 2,
      "True and False are boolean (bool) values."),
    Q("How do you write a single-line comment in Python?",
      ["// This is a comment", "# This is a comment", "/* This is a comment */", "-- This is a comment"], 1,
      "Python comments start with #."),
    Q("What does the input() function return by default?", ["integer", "float", "string", "boolean"], 2,
      "input() always returns a string; convert it with int() or float() when needed."),
    Q("Which of the following is correct indentation?",
      ["if age >= 18:\n    print('Adult')", "if age >= 18:\nprint('Adult')", "Both a and b", "None of the above"], 0,
      "The statement inside the if block must be indented."),
    Q("What is the result of 17 % 5?", ["3", "2", "3.4", "5"], 1,
      "17 = 5 x 3 + 2, so the remainder is 2."),
]

# ==========================================================================
#  PROGRESSION LOGIC
# ==========================================================================
def lesson_by_id(lid):
    return LESSONS[lid - 1]


def sections_complete(student, L):
    st = lesson_state(student, L["id"])
    return len(set(st["sections"])) >= len(L["sections"])


def quiz_passed(st):
    return (st["quiz_best"] or 0) >= PASS_PCT


def is_unlocked(student, lid):
    return lid == 1 or lesson_state(student, lid - 1)["completed"]


def lesson_steps(student, L):
    """(steps done, total steps): every section + the activity + the quiz."""
    st = lesson_state(student, L["id"])
    done = len(set(st["sections"])) + (1 if st["activity"] else 0) + (1 if quiz_passed(st) else 0)
    return done, len(L["sections"]) + 2


def all_completed(student):
    return all(lesson_state(student, L["id"])["completed"] for L in LESSONS)


def check_completion(student, L):
    """Mark a lesson complete when sections + activity + quiz are all done."""
    st = lesson_state(student, L["id"])
    if st["completed"]:
        return False
    if sections_complete(student, L) and st["activity"] and quiz_passed(st):
        st["completed"] = True
        st["completed_on"] = date.today().isoformat()
        save_data()
        return True
    return False


def average_quiz(student):
    scores = [lesson_state(student, L["id"])["quiz_best"] or 0 for L in LESSONS]
    return round(sum(scores) / len(scores)) if scores else 0


# ==========================================================================
#  LESSON SECTIONS VIEWER
# ==========================================================================
def view_sections(student, L, start=0):
    secs = L["sections"]
    i = start
    st = lesson_state(student, L["id"])
    while 0 <= i < len(secs):
        if i not in st["sections"]:
            st["sections"].append(i)
            save_data()
        clear()
        topbar(student, "Home", f"Lesson {L['id']}", f"Section {i + 1}/{len(secs)}")
        print()
        print("  " + paint(f"LESSON {L['id']} : {L['title']}", C.GOLDB))
        print("  " + bar(i + 1, len(secs), 20) + paint(f"  section {i + 1} of {len(secs)}: {secs[i]['title']}", C.DIM))
        render_blocks(secs[i]["blocks"])
        print()
        rule()
        last = i == len(secs) - 1
        nxt = "finish" if last else "next"
        cmd = ask("  " + paint(f"[Enter] {nxt}  ·  [b] back  ·  [1-{len(secs)}] jump  ·  [m] lesson menu  ▸ ", C.GOLD)).strip().lower()
        if cmd in ("m", "x", "menu"):
            return
        if cmd == "b":
            i = max(0, i - 1)
        elif cmd.isdigit() and 1 <= int(cmd) <= len(secs):
            i = int(cmd) - 1
        else:  # Enter or anything else = next
            i += 1


# ==========================================================================
#  CODING ACTIVITY
# ==========================================================================
def check_test(t, out, err, rc):
    if rc is None:
        return False, "Your program ran for too long (is there an infinite loop?)."
    if rc != 0:
        msg = last_error_line(err)
        if "EOFError" in msg:
            msg = "Your program asked for more input() than expected."
        return False, f"Error: {msg}"
    lines = [ln.rstrip() for ln in out.strip().splitlines()]
    if t["mode"] == "exact":
        if lines == t["expect"]:
            return True, ""
        return False, ("Expected: " + " / ".join(t["expect"]) + "\n      Your output: "
                       + (" / ".join(lines) if lines else "(nothing printed)"))
    last = lines[-1] if lines else ""
    if last.endswith(t["expect"]):
        return True, ""
    return False, f"Expected the output to end with: {t['expect']}\n      Your output ended with: {last or '(nothing)'}"


def evaluate_activity(code, act):
    """Return (passed, list of display lines)."""
    lines = []
    missing = [msg for rx, msg in act.get("needs", []) if not re.search(rx, code)]
    if missing:
        return False, [paint("  ✖ " + m, C.BAD) for m in missing]
    passed_all = True
    first_reason = None
    for n, t in enumerate(act["tests"], 1):
        stdin = "\n".join(t["inp"]) + "\n" if t["inp"] else ""
        out, err, rc = run_python(code, stdin)
        ok, why = check_test(t, out, err, rc)
        label = "input: " + ", ".join(t["inp"]) if t["inp"] else "no input needed"
        mark = paint("✔", C.OK) if ok else paint("✖", C.BAD)
        lines.append(f"  {mark} Test {n}  ({label})")
        if not ok:
            passed_all = False
            first_reason = first_reason or why
    if first_reason:
        lines.append("")
        lines.append(paint("    " + first_reason, C.BAD))
    return passed_all, lines


def read_code(act, attempts):
    """Read multi-line code from the user. Returns the code, or None to leave."""
    print("  " + paint("Type your code line by line (keep your own indentation).", C.DIM))
    print("  " + paint("Commands on their own line:  DONE = run   HINT   SOLUTION   QUIT", C.GOLD))
    print()
    lines = []
    while True:
        raw = ask(paint(f"{len(lines) + 1:>3} │ ", C.DIM))
        cmd = raw.strip().upper()
        if cmd == "DONE":
            if not any(ln.strip() for ln in lines):
                print("  " + paint("Nothing to run yet - type some code first.", C.BAD))
                continue
            return "\n".join(lines)
        if cmd == "QUIT":
            return None
        if cmd == "HINT":
            print("  " + paint("HINT: " + act["hint"], C.GOLD))
            continue
        if cmd == "SOLUTION":
            if attempts >= 3:
                panel("SOLUTION", act["solution"].splitlines(), C.CODE, numbered=True)
            else:
                print("  " + paint(f"The solution unlocks after 3 failed runs (you have {attempts}).", C.BAD))
            continue
        lines.append(raw.replace("\t", "    "))


def activity_screen(student, L):
    act = L["activity"]
    st = lesson_state(student, L["id"])
    attempts = 0
    while True:
        clear()
        topbar(student, "Home", f"Lesson {L['id']}", "Coding Activity")
        print()
        print("  " + paint(f"CODING ACTIVITY - {L['title']}", C.GOLDB))
        if st["activity"]:
            print("  " + paint("✔ Already passed - you can practise again.", C.OK))
        print()
        for ln in act["task"]:
            print("  " + ln)
        print()
        rule()
        code = read_code(act, attempts)
        if code is None:
            return
        print()
        passed, lines = evaluate_activity(code, act)
        for ln in lines:
            print(ln)
        print()
        if passed:
            st["activity"] = True
            save_data()
            print("  " + paint("★ Activity passed! Your program works as required.", C.OK))
            pause()
            return
        attempts += 1
        print("  " + paint("Not quite yet - read the message above and try again.", C.GOLD))
        if attempts >= 3:
            print("  " + paint("Tip: type SOLUTION in the editor to see a working answer.", C.DIM))
        if ask("\n  " + paint("[Enter] try again  ·  [q] back to lesson menu ▸ ", C.GOLD)).strip().lower() == "q":
            return


# ==========================================================================
#  QUIZ ENGINE
# ==========================================================================
def run_quiz(student, title, questions, crumbs, verdicts=None):
    """Run a multiple-choice quiz. Returns the percentage, or None if abandoned."""
    order = list(questions)
    random.shuffle(order)
    score = 0
    total = len(order)
    for n, q in enumerate(order, 1):
        opts = list(enumerate(q["opts"]))
        random.shuffle(opts)
        letters = string.ascii_lowercase[:len(opts)]
        correct = letters[[o[0] for o in opts].index(q["ans"])]
        clear()
        topbar(student, *crumbs)
        print()
        print("  " + paint(title, C.GOLDB) + paint(f"   question {n}/{total}   score {score}", C.DIM))
        print("  " + bar(n - 1, total, 20))
        print()
        for ln in textwrap.wrap(f"{n}. {q['q']}", term_width() - 6):
            print("  " + paint(ln, C.B))
        if q.get("code"):
            print()
            panel("PYTHON CODE", q["code"].splitlines(), C.CODE, numbered=True)
        print()
        for letter, (_, text) in zip(letters, opts):
            parts = text.split("\n")
            print("   " + paint(f"{letter})", C.BLUE) + " " + parts[0])
            for extra in parts[1:]:
                print("      " + extra)
        print()
        while True:
            a = ask("  " + paint(f"Your answer ({'/'.join(letters)}, or q to quit) ▸ ", C.GOLD)).strip().lower()
            if a == "q":
                if ask("  Quit this quiz? Your attempt will not be saved (y/n) ▸ ").strip().lower() == "y":
                    return None
                continue
            if a in letters:
                break
            print("  " + paint(f"Please type one of: {', '.join(letters)}", C.BAD))
        print()
        if a == correct:
            score += 1
            print("  " + paint("✔ Correct!", C.OK))
        else:
            right_text = dict(zip(letters, [o[1] for o in opts]))[correct].replace("\n", " ")
            print("  " + paint(f"✖ Not quite. The correct answer is {correct}) {right_text}", C.BAD))
        for ln in textwrap.wrap(q["why"], term_width() - 6):
            print("  " + paint(ln, C.DIM))
        if n < total:
            pause("Press Enter for the next question...")
    pct = round(100 * score / total)
    clear()
    topbar(student, *crumbs)
    print()
    print("  " + paint(f"{title} - RESULTS", C.GOLDB))
    rule("═", C.GOLD)
    print(f"  Your score: {paint(f'{score}/{total}', C.B)}    Percentage: {paint(f'{pct}%', C.B)}")
    print("  " + bar(score, total, 30))
    print()
    if verdicts:
        msg, col = (verdicts[0], C.OK) if pct >= 90 else (verdicts[1], C.GOLD) if pct >= 70 else (verdicts[2], C.BAD)
        print("  " + paint(msg, col))
    elif pct >= PASS_PCT:
        print("  " + paint(f"★ PASSED! You reached the required {PASS_PCT}%.", C.OK))
    else:
        print("  " + paint(f"✖ Not passed yet - you need at least {PASS_PCT}%. Review the lesson and try again.", C.BAD))
    rule("═", C.GOLD)
    return pct


def lesson_quiz(student, L):
    st = lesson_state(student, L["id"])
    pct = run_quiz(student, f"QUIZ - LESSON {L['id']}", L["quiz"], ["Home", f"Lesson {L['id']}", "Quiz"])
    if pct is None:
        return
    st["quiz_attempts"] += 1
    st["quiz_best"] = max(st["quiz_best"] or 0, pct)
    save_data()
    if pct >= PASS_PCT and check_completion(student, L):
        pause("Press Enter to continue...")
        lesson_complete_screen(student, L)
    else:
        if pct >= PASS_PCT and not st["completed"]:
            print("  " + paint("Quiz passed! Finish the remaining parts of this lesson to complete it.", C.GOLD))
        pause("Press Enter to return to the lesson menu...")


def adventure_mode(student):
    verdicts = ("Excellent! You have a strong understanding of the Prelim topics, Galing!",
                "Good job! Review the topics you missed (huhu).",
                "Keep practicing! Review mo yung lesson ulit!")
    pct = run_quiz(student, "ADVENTURE MODE - ACT 102", ADVENTURE, ["Home", "Prelim", "Adventure Mode"], verdicts)
    if pct is not None:
        student["adventure_best"] = max(student.get("adventure_best") or 0, pct)
        save_data()
        pause("Press Enter to go back to Prelim Menu...")


# ==========================================================================
#  LESSON COMPLETE + CERTIFICATE
# ==========================================================================
def lesson_complete_screen(student, L):
    clear()
    topbar(student, "Home", f"Lesson {L['id']}", "Completed")
    w = term_width()
    print()
    print(paint("  ╔" + "═" * (w - 6) + "╗", C.OK))
    print(paint("  ║", C.OK) + center_v(paint(f"★  LESSON {L['id']} COMPLETED  ★", C.OK), w - 6) + paint("║", C.OK))
    print(paint("  ╚" + "═" * (w - 6) + "╝", C.OK))
    print()
    print("  " + L["title"])
    done = sum(1 for x in LESSONS if lesson_state(student, x["id"])["completed"])
    print("  " + bar(done, len(LESSONS), 30) + paint(f"  {done}/{len(LESSONS)} lessons", C.DIM))
    print()
    if all_completed(student):
        pause("Press Enter to receive your certificate...")
        award_certificate(student)
    else:
        nxt = lesson_by_id(L["id"] + 1)
        print("  " + paint(f"Unlocked: Lesson {nxt['id']} - {nxt['title']}", C.GOLD))
        pause()


def cert_path(student):
    safe = re.sub(r"[^A-Za-z0-9]+", "_", student["name"]).strip("_") or "student"
    return DATA_DIR / f"ACT102_Certificate_{safe}.html"


CERT_HTML = string.Template("""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Certificate of Completion - $name</title>
<style>
  body{margin:0;background:#0d1b3d;font-family:Georgia,'Times New Roman',serif;color:#1c2540;padding:24px}
  .cert{max-width:900px;margin:0 auto;background:#fffdf6;border:14px double #c9a227;padding:48px 56px;text-align:center}
  .small{letter-spacing:.25em;font-size:13px;color:#6b7390;text-transform:uppercase}
  h1{font-size:44px;color:#0d1b3d;margin:14px 0 6px;letter-spacing:.06em}
  .name{font-size:38px;color:#a07d10;border-bottom:2px solid #c9a227;display:inline-block;padding:4px 36px;margin:14px 0}
  p{font-size:17px;line-height:1.6;margin:8px 0}
  table{margin:20px auto;border-collapse:collapse;font-size:14px;width:100%}
  th,td{border-bottom:1px solid #e4dcc0;padding:6px 10px;text-align:left}
  th{color:#6b7390;text-transform:uppercase;font-size:12px;letter-spacing:.1em}
  td.s{text-align:right;color:#2e7d4f;font-weight:bold}
  .foot{display:flex;justify-content:space-between;margin-top:30px;font-size:13px;color:#6b7390}
  button{margin-top:22px;padding:10px 22px;font-size:15px;background:#0d1b3d;color:#f5d76e;border:0;cursor:pointer}
  @media print{body{background:#fff;padding:0}button{display:none}}
</style></head><body><div class="cert">
  <div class="small">Associate in Computer Technology I</div>
  <h1>CERTIFICATE OF COMPLETION</h1>
  <p>This certifies that</p>
  <div class="name">$name</div>
  <p>has successfully completed all lessons, coding activities and quizzes of<br>
  <b>ACT 102 - Fundamentals of Programming (Python)</b><br>
  with an average quiz score of <b>$avg%</b>.</p>
  <table><tr><th>Lesson</th><th>Title</th><th style="text-align:right">Best quiz score</th></tr>
  $rows</table>
  <div class="foot"><span>Date awarded: $date</span><span>Certificate ID: $cid</span></div>
  <button onclick="window.print()">Print / Save as PDF</button>
</div></body></html>""")


def write_certificate_html(student):
    cert = student["certificate"]
    rows = "".join(
        f"<tr><td>Lesson {L['id']}</td><td>{html.escape(L['title'])}</td>"
        f"<td class='s'>{lesson_state(student, L['id'])['quiz_best']}%</td></tr>" for L in LESSONS)
    page = CERT_HTML.substitute(name=html.escape(student["name"]), avg=average_quiz(student),
                                rows=rows, date=html.escape(cert["date"]), cid=html.escape(cert["id"]))
    path = cert_path(student)
    path.write_text(page, encoding="utf-8")
    return path


def award_certificate(student, reopen=False):
    if not student.get("certificate"):
        stamp = date.today().strftime("%Y%m%d")
        digest = hashlib.sha1((student["name"] + stamp).encode("utf-8")).hexdigest()[:6].upper()
        student["certificate"] = {"id": f"ACT102-{stamp}-{digest}", "date": date.today().isoformat()}
        save_data()
    cert = student["certificate"]
    try:
        path = write_certificate_html(student)
    except OSError as e:
        path = None
        print(paint(f"  Could not write the certificate file: {e}", C.BAD))
    clear()
    topbar(student, "Home", "Certificate")
    w = min(term_width(), 76)
    pad = " " * ((term_width() - w) // 2)
    box = [paint("╔" + "═" * (w - 2) + "╗", C.GOLD)]

    def line(txt=""):
        box.append(paint("║", C.GOLD) + center_v(txt, w - 2) + paint("║", C.GOLD))
    line(); line(paint("ASSOCIATE IN COMPUTER TECHNOLOGY I", C.DIM)); line()
    line(paint("CERTIFICATE OF COMPLETION", C.GOLDB)); line()
    line("This certifies that"); line()
    line(paint(student["name"].upper(), C.PINK)); line()
    line("has successfully completed")
    line(paint("ACT 102 - FUNDAMENTALS OF PROGRAMMING", C.B))
    line("all 8 lessons, coding activities and quizzes"); line()
    line(f"Average quiz score: {average_quiz(student)}%"); line()
    line(paint(f"Date: {cert['date']}    ID: {cert['id']}", C.DIM)); line()
    box.append(paint("╚" + "═" * (w - 2) + "╝", C.GOLD))
    print()
    for b in box:
        print(pad + b)
    print()
    if path:
        print("  " + paint("✔ Certificate file saved:", C.OK) + " " + str(path))
        print("  " + paint("  Open it in your browser and use Print / Save as PDF.", C.DIM))
        try:
            webbrowser.open(path.as_uri())
        except Exception:
            pass
    pause("Press Enter to return to the main menu...")


# ==========================================================================
#  MENUS
# ==========================================================================
def lesson_hub(student, L):
    msg = ""
    while True:
        st = lesson_state(student, L["id"])
        secs_ok = sections_complete(student, L)
        quiz_ok = quiz_passed(st)
        clear()
        topbar(student, "Home", f"Lesson {L['id']}")
        done, total = lesson_steps(student, L)
        print()
        print("  " + paint(f"LESSON {L['id']} : {L['title']}", C.GOLDB))
        print("  " + bar(done, total, 28) + paint(f"  {round(100 * done / total)}% complete", C.DIM))
        if st["completed"]:
            print("  " + paint("✔ Lesson completed - open anything below to review.", C.OK))
        print()
        print("  " + paint("1. LEARN", C.HEAD))
        for i, s in enumerate(L["sections"]):
            mark = paint("✔", C.OK) if i in st["sections"] else paint("○", C.DIM)
            print(f"   [{i + 1}] {mark} {s['title']}")
        print()
        print("  " + paint("2. PRACTISE", C.HEAD))
        if not secs_ok:
            status = paint("locked - read every section first", C.DIM)
        elif st["activity"]:
            status = paint("✔ passed", C.OK)
        else:
            status = paint("▶ ready", C.GOLD)
        print(f"   [a] Coding activity   {status}")
        print()
        print("  " + paint("3. TEST", C.HEAD))
        if not (secs_ok and st["activity"]):
            status = paint("locked - pass the coding activity first", C.DIM)
        elif quiz_ok:
            status = paint(f"✔ passed (best {st['quiz_best']}%)", C.OK)
        elif st["quiz_attempts"]:
            status = paint(f"best {st['quiz_best']}% - need {PASS_PCT}%", C.BAD)
        else:
            status = paint("▶ ready", C.GOLD)
        print(f"   [q] Lesson quiz       {status}")
        print()
        print(paint("   [s] Continue studying   ", C.GOLD) + paint("[x] Back", C.BAD))
        if msg:
            print("\n  " + msg)
            msg = ""
        rule()
        c = ask("  " + paint("Choose ▸ ", C.GOLD)).strip().lower()
        if c == "x":
            return
        elif c == "s":
            unread = [i for i in range(len(L["sections"])) if i not in st["sections"]]
            view_sections(student, L, unread[0] if unread else 0)
            if sections_complete(student, L) and not st["activity"]:
                msg = paint("All sections read - the coding activity is now unlocked!", C.OK)
        elif c.isdigit() and 1 <= int(c) <= len(L["sections"]):
            view_sections(student, L, int(c) - 1)
            if sections_complete(student, L) and not st["activity"]:
                msg = paint("All sections read - the coding activity is now unlocked!", C.OK)
        elif c == "a":
            if not secs_ok:
                msg = paint("Read every section first to unlock the coding activity.", C.BAD)
            else:
                activity_screen(student, L)
                if check_completion(student, L):  # (quiz may already have been passed)
                    lesson_complete_screen(student, L)
        elif c == "q":
            if not (secs_ok and st["activity"]):
                msg = paint("Pass the coding activity first to unlock the quiz.", C.BAD)
            else:
                lesson_quiz(student, L)
        else:
            msg = paint("Invalid choice. Please pick a listed option.", C.BAD)


def lesson_status_text(student, L):
    st = lesson_state(student, L["id"])
    if st["completed"]:
        return paint("✔ Completed", C.OK)
    if not is_unlocked(student, L["id"]):
        return paint(f"✖ Locked (finish Lesson {L['id'] - 1} first)", C.DIM)
    done, total = lesson_steps(student, L)
    return paint(f"▶ {round(100 * done / total)}% done" if done else "▶ Ready to start", C.GOLD)


def term_menu(student, term):
    msg = ""
    letters = string.ascii_lowercase
    while True:
        clear()
        topbar(student, "Home", term["name"].title())
        print()
        print("  " + paint(f"CHOOSE {term['name']} LESSON:", C.HEAD))
        print()
        for i, lid in enumerate(term["lessons"]):
            L = lesson_by_id(lid)
            print(f"   {paint('[' + letters[i] + ']', C.BLUE)} LESSON {lid} : {L['title']}")
            print(f"        {lesson_status_text(student, L)}")
        if term["name"] == "PRELIM":
            print(f"\n   {paint('[e]', C.OK)} {paint('TRY ADVENTURE MODE ( Simple Quiz! )', C.OK)}"
                  + paint(f"   best: {student['adventure_best']}%" if student.get("adventure_best") is not None else "", C.DIM))
        print(f"\n   {paint('[x] Back to Main Menu', C.BAD)}")
        if msg:
            print("\n  " + msg)
            msg = ""
        rule()
        c = ask("  " + paint("Choose ▸ ", C.GOLD)).strip().lower()
        if c == "x":
            return
        if term["name"] == "PRELIM" and c == "e":
            adventure_mode(student)
        elif len(c) == 1 and c in letters and letters.index(c) < len(term["lessons"]):
            lid = term["lessons"][letters.index(c)]
            if is_unlocked(student, lid):
                lesson_hub(student, lesson_by_id(lid))
            else:
                msg = paint(f"Lesson {lid} is locked. Complete Lesson {lid - 1} "
                            "(all sections, the activity and the quiz) first.", C.BAD)
        else:
            msg = paint("Invalid choice. Please pick a listed option.", C.BAD)


def progress_screen(student):
    msg = ""
    while True:
        clear()
        topbar(student, "Home", "My Progress")
        done = sum(1 for L in LESSONS if lesson_state(student, L["id"])["completed"])
        print()
        print("  " + paint("MY PROGRESS", C.GOLDB))
        print("  " + bar(done, len(LESSONS), 30) + paint(f"  {done}/{len(LESSONS)} lessons completed", C.DIM))
        print()
        rows = []
        for L in LESSONS:
            st = lesson_state(student, L["id"])
            qb = f"{st['quiz_best']}%" if st["quiz_best"] is not None else "-"
            rows.append([f"{L['id']}", L["title"][:38],
                         f"{len(set(st['sections']))}/{len(L['sections'])}",
                         paint("✔", C.OK) if st["activity"] else "-", qb, str(st["quiz_attempts"]),
                         lesson_status_text(student, L)])
        table(["#", "Lesson", "Read", "Activity", "Quiz best", "Tries", "Status"], rows)
        print()
        adv = student.get("adventure_best")
        print("  Adventure Mode best: " + (f"{adv}%" if adv is not None else "not tried yet") + paint("  (optional bonus)", C.DIM))
        cert = student.get("certificate")
        print("  Certificate: " + (paint(f"✔ awarded {cert['date']} ({cert['id']})", C.OK) if cert
                                   else paint("not yet - complete all lessons and quizzes", C.DIM)))
        if msg:
            print("\n  " + msg)
            msg = ""
        print()
        rule()
        c = ask("  " + paint("[x] back  ·  [r] reset my progress ▸ ", C.GOLD)).strip().lower()
        if c == "x":
            return
        if c == "r":
            if ask("  Type RESET to erase ALL of your progress (cannot be undone) ▸ ").strip() == "RESET":
                student["lessons"] = {}
                student["adventure_best"] = None
                student["certificate"] = None
                save_data()
                msg = paint("Progress has been reset.", C.OK)
            else:
                msg = paint("Reset cancelled.", C.GOLD)
        else:
            msg = paint("Invalid choice.", C.BAD) if c else ""


def certificate_screen(student):
    if all_completed(student):
        award_certificate(student)
        return
    clear()
    topbar(student, "Home", "Certificate")
    print()
    print("  " + paint("CERTIFICATE OF COMPLETION", C.GOLDB))
    print("  " + paint("Not available yet. Finish every lesson, coding activity and quiz to earn it.", C.DIM))
    print()
    for L in LESSONS:
        st = lesson_state(student, L["id"])
        mark = paint("✔", C.OK) if st["completed"] else paint("○", C.DIM)
        print(f"   {mark} Lesson {L['id']} : {L['title']}")
    pause("Press Enter to return to the main menu...")


def choose_student():
    msg = ""
    while True:
        clear()
        main_banner()
        print()
        names = sorted(DATA["students"].values(), key=lambda s: s["name"].lower())
        print("  " + paint("WHO IS LEARNING TODAY?", C.HEAD))
        if names:
            print()
            for i, s in enumerate(names, 1):
                done = sum(1 for L in LESSONS if lesson_state(s, L["id"])["completed"])
                print(f"   [{i}] {s['name']}  " + paint(f"({done}/{len(LESSONS)} lessons)", C.DIM))
            print("\n  Type a number to continue, or type a new full name to create a profile.")
        else:
            print("\n  Welcome! Type your full name to create your learner profile.")
        if msg:
            print("\n  " + msg)
            msg = ""
        print()
        raw = ask("  " + paint("Name ▸ ", C.GOLD)).strip()
        if not raw:
            msg = paint("Please enter a name.", C.BAD)
            continue
        if raw.isdigit() and names and 1 <= int(raw) <= len(names):
            return names[int(raw) - 1]
        if len(raw) > 40:
            msg = paint("Please use 40 characters or fewer.", C.BAD)
            continue
        key = raw.lower()
        if key not in DATA["students"]:
            DATA["students"][key] = new_student(raw)
            save_data()
        return DATA["students"][key]


def main_menu(student):
    msg = ""
    while True:
        clear()
        main_banner()
        done = sum(1 for L in LESSONS if lesson_state(student, L["id"])["completed"])
        print("\n  " + paint(f"Welcome, {student['name']}!", C.B) + "  "
              + bar(done, len(LESSONS), 20) + paint(f"  {done}/{len(LESSONS)} lessons", C.DIM))
        print("\n  " + paint("CHOOSE:", C.HEAD))
        for key, term in zip("123", TERMS):
            n_done = sum(1 for lid in term["lessons"] if lesson_state(student, lid)["completed"])
            label = ljust_v(paint(term["name"], C.GOLD), 14)
            print(f"   {paint(key + '.', C.GOLD)} {label}"
                  + paint(f"{n_done}/{len(term['lessons'])} lessons", C.DIM))
        print(f"   {paint('4.', C.BLUE)} {paint('MY PROGRESS', C.BLUE)}")
        print(f"   {paint('5.', C.OK)} {paint('CERTIFICATE', C.OK)}"
              + (paint("  ★ ready!", C.GOLDB) if all_completed(student) else ""))
        print(f"   {paint('6.', C.DIM)} SWITCH STUDENT")
        print(f"   {paint('0. EXIT', C.BAD)}")
        if msg:
            print("\n  " + msg)
            msg = ""
        print()
        rule("_")
        c = ask("  " + paint("Search ▸ ", C.GOLD)).strip()
        if c == "0":
            clear()
            print("\n  Thank you for using the ACT 102 Learning System. Goodbye!\n")
            return
        elif c in ("1", "2", "3"):
            term_menu(student, TERMS[int(c) - 1])
        elif c == "4":
            progress_screen(student)
        elif c == "5":
            certificate_screen(student)
        elif c == "6":
            student = choose_student()
        else:
            msg = paint("Invalid choice. Please enter 1, 2, 3, 4, 5, 6, or 0.", C.BAD)


# ==========================================================================
#  SELF-TEST  (python act102.py --selftest)
# ==========================================================================
def selftest():
    problems = 0
    print("Checking lesson data...")
    for L in LESSONS:
        for qn, q in enumerate(L["quiz"], 1):
            if not 0 <= q["ans"] < len(q["opts"]) or len(q["opts"]) < 2:
                print(f"  ✖ Lesson {L['id']} quiz Q{qn}: bad answer index"); problems += 1
        ok, lines = evaluate_activity(L["activity"]["solution"], L["activity"])
        flag = "✔" if ok else "✖"
        print(f"  {flag} Lesson {L['id']}: reference solution passes all activity tests")
        if not ok:
            problems += 1
            print("\n".join(lines))
        # a wrong program must NOT pass
        bad, _ = evaluate_activity('print("wrong")', L["activity"])
        if bad:
            print(f"  ✖ Lesson {L['id']}: a wrong program was accepted"); problems += 1
        # every live demo must run
        for s in L["sections"]:
            for blk in s["blocks"]:
                if blk[0] == "demo":
                    src = (ECHO_PRELUDE + blk[1]) if blk[2] else blk[1]
                    out, err, rc = run_python(src, "\n".join(blk[2]) + "\n" if blk[2] else "")
                    expected_error = any(w in blk[1] for w in ("print(Name)", "print(Hello, World!)",
                                                              "age + 1")) or \
                        (blk[1].count("\n") == 2 and "if age >= 18:\nprint" in blk[1])
                    if rc != 0 and not expected_error:
                        print(f"  ✖ Lesson {L['id']} / {s['title']}: demo failed: {last_error_line(err)}")
                        problems += 1
    for qn, q in enumerate(ADVENTURE, 1):
        if not 0 <= q["ans"] < len(q["opts"]):
            print(f"  ✖ Adventure Q{qn}: bad answer index"); problems += 1
    print("\n" + ("All checks passed." if not problems else f"{problems} problem(s) found."))
    return problems == 0


# ==========================================================================
#  MAIN
# ==========================================================================
def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    try:
        student = choose_student()
        main_menu(student)
    except Quit:
        print("\n\n  Progress is saved. Goodbye!\n")


if __name__ == "__main__":
    main()