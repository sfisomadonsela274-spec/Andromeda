import os

with open('index.html', 'r') as f:
    lines = f.readlines()

style_start = -1
style_end = -1
script_start = -1
script_end = -1

for i, line in enumerate(lines):
    if '<style>' in line:
        style_start = i
    elif '</style>' in line:
        style_end = i
    elif '<script>' in line:
        script_start = i
    elif '</script>' in line:
        script_end = i

if style_start != -1 and style_end != -1:
    style_content = "".join(lines[style_start+1:style_end])
    # Prepend tailwind imports
    style_content = '@import "tailwindcss";\n' + style_content
    with open('src/style.css', 'w') as f:
        f.write(style_content)

if script_start != -1 and script_end != -1:
    script_content = "".join(lines[script_start+1:script_end])
    with open('src/main.js', 'w') as f:
        f.write(script_content)

# Now construct the new HTML
new_html = []
i = 0
while i < len(lines):
    if i == style_start:
        new_html.append('    <link rel="stylesheet" href="/src/style.css">\n')
        i = style_end + 1
        continue
    if i == script_start:
        new_html.append('    <script type="module" src="/src/main.js"></script>\n')
        i = script_end + 1
        continue
    new_html.append(lines[i])
    i += 1

with open('index.html', 'w') as f:
    f.writelines(new_html)
