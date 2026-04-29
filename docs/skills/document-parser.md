# Document Parser Skill

## ParsedDocument dataclass
```python
@dataclass
class Section:
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)

@dataclass
class ParsedDocument:
    title: str
    sections: list[Section]
    word_count: int
    raw_text: str = ""

    def preview(self, max_words=500) -> str:
        return " ".join(self.raw_text.split()[:max_words])

    def to_prompt_text(self) -> str:
        out = ""
        for s in self.sections:
            out += f"\n## {s.heading}\n"
            for p in s.paragraphs: out += f"{p}\n"
            for b in s.bullets: out += f"- {b}\n"
        return out
```

## PDF (pdfplumber)
```python
with pdfplumber.open(io.BytesIO(data)) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped: continue
            if len(stripped) < 80 and stripped.isupper():
                sections.append(current); current = Section(heading=stripped)
            else:
                current.paragraphs.append(stripped)
        for table in (page.extract_tables() or []):
            current.tables.append(table)
```

## DOCX (python-docx)
```python
doc = Document(io.BytesIO(data))
HEADING = {"Heading 1","Heading 2","Heading 3","Title"}
BULLET  = {"List Bullet","List Bullet 2","List Paragraph"}
for para in doc.paragraphs:
    t = para.text.strip()
    if not t: continue
    if para.style.name in HEADING:
        sections.append(current); current = Section(heading=t)
    elif para.style.name in BULLET:
        current.bullets.append(t)
    else:
        current.paragraphs.append(t)
for table in doc.tables:
    rows = [[c.text for c in r.cells] for r in table.rows]
    current.tables.append(rows)
```

## TXT/MD (markdown-it-py)
```python
from markdown_it import MarkdownIt
md = MarkdownIt()
tokens = md.parse(text)
for token in tokens:
    if token.type == "heading_open":
        heading_level = token.tag  # h1, h2, h3
    elif token.type == "inline" and prev == "heading_open":
        sections.append(current)
        current = Section(heading=token.content)
    elif token.type == "inline":
        current.paragraphs.append(token.content)
```

## Validation
- If word_count < 50 after parse: raise ValueError("Document too short")
- If len(sections) == 0: wrap all text in single Section("Document")
- Cap sections at 50 to prevent oversized prompts
