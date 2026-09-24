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
        # find each @xxx.route(...) followed by def name(...): ... until next @ or EOF
        pattern = re.compile(r'@\w+\.route\([^)]*methods=\[[^\]]*[\'"]POST[\'"][^\]]*\][^)]*\)\s*\n(?:@\w+[^\n]*\n)*def (\w+)\(([^)]*)\):', re.M)
        for m in pattern.finditer(src):
            total_post_routes += 1
            start = m.end()
            # grab next ~2500 chars or until next top-level def/route as a rough function body
            rest = src[start:start+3000]
            next_def = re.search(r'\n@\w+\.route\(|\n\ndef \w+\(', rest)
            body = rest[:next_def.start()] if next_def else rest
            has_csrf = "validate_csrf" in body
            has_no_csrf_marker = "no csrf" in body.lower() or "csrf-exempt" in body.lower()
            if not has_csrf:
                missing.append((path, m.group(1), has_no_csrf_marker))

print(f"Total POST route functions scanned: {total_post_routes}")
print(f"POST routes with NO validate_csrf call in body: {len(missing)}\n")
for path, name, marker in missing:
    print(f"{path} :: {name}  {'(explicitly marked no-csrf)' if marker else ''}")
