import os

targets = ["âœ…", "ðŸš¨", "â‚¹", "ðŸ™", "âš ", "âž”", "â„¹"]

for root, dirs, files in os.walk("."):
    if "node_modules" in root or "venv" in root or ".git" in root:
        continue
    for file in files:
        if file.endswith((".py", ".md", ".json", ".js", ".jsx", ".html", ".sql", ".css")):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for t in targets:
                    if t in content:
                        print(f"Found '{t}' in {path}")
            except Exception as e:
                pass
