import re, os

root = "app/blueprints"
missing = []
total_post_routes = 0

for dirpath, _, files in os.walk(root):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        with open(path, encoding="utf-8") as f:
            src = f.read()
        pattern = re.compile(r'@\w+\.route\([^)]*methods=\[[^\]]*[\'"]POST[\'"][^\]]*\][^)]*\)\s*\n(?:@\w+[^\n]*\n)*def (\w+)\(([^)]*)\):', re.M)
        for m in pattern.finditer(src):
            total_post_routes += 1
            start = m.end()
            rest = src[start:start+3000]
            next_def = re.search(r'\n@\w+\.route\(|\n\ndef \w+\(', rest)
            body = rest[:next_def.start()] if next_def else rest
            has_csrf = re.search(r'csrf', body, re.I) is not None
            if not has_csrf:
                missing.append((path, m.group(1)))

print(f"Total POST route functions scanned: {total_post_routes}")
print(f"POST routes with NO 'csrf' (any casing) mentioned in body: {len(missing)}\n")
for path, name in missing:
    print(f"{path} :: {name}")
