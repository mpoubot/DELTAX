"""E40/E42: a test appended after the summary print runs but is never counted.
This guards every test file against that silent-green failure mode."""
import glob, re
passed = failed = 0
def check(c, name, detail=""):
    global passed, failed
    print(f"  {'✓' if c else '✗'} {name}{'  ' + detail if detail else ''}")
    if c: passed += 1
    else: failed += 1

print("── no test defined after its own summary print ──")
for f in sorted(glob.glob("tests/test_*.py")):
    if f.endswith("test_meta.py"):
        continue
    lines = open(f).read().split("\n")
    # dead code after sys.exit() never runs, however green the file looks
    exits = [i for i, l in enumerate(lines) if l.strip().startswith("sys.exit(")]
    if exits:
        after = [i + 1 for i, l in enumerate(lines[exits[-1] + 1:], start=exits[-1] + 1)
                 if l.strip() and not l.strip().startswith("#")]
        check(not after, f"{f.split('/')[-1]:<22} no code after sys.exit",
              "clean" if not after else f"DEAD CODE at line {after}")

    dupes = [i + 1 for i, l in enumerate(lines)
             if "{passed} passed" in l and "print" in l]
    check(len(dupes) <= 1, f"{f.split('/')[-1]:<22} single summary print",
          "clean" if len(dupes) <= 1 else f"{len(dupes)} summaries at {dupes}")

    summary = [i for i, l in enumerate(lines)
               if re.search(r"passed.*failed", l) and "print" in l]
    if not summary:
        check(True, f"{f.split('/')[-1]:<22} nothing after the counter",
              "no summary print")
        continue
    last = summary[-1]
    orphans = [i + 1 for i, l in enumerate(lines[last + 1:], start=last + 1)
               if re.match(r"^(test_\w+\(\)|def test_)", l)]
    orphans += [i + 1 for i, l in enumerate(lines[last + 1:], start=last + 1)
                if re.match(r"^\s*check\(", l)]
    check(not orphans, f"{f.split('/')[-1]:<22} nothing after the counter",
          "clean" if not orphans else f"UNCOUNTED at line {sorted(orphans)}")

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
