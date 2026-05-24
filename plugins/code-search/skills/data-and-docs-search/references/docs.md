# documents (`rga`, `pdftotext`, `pandoc`)

Search and extract text from binary/rich documents: PDFs, Office files, archives.

## rga (ripgrep-all) — grep inside non-text files

`rga` is `rg` with adapters that transparently extract text from PDFs, `.docx`,
`.xlsx`, `.pptx`, `.zip`/`.tar.gz`, `.sqlite`, `.epub`, and more. It accepts the
same flags as `rg`.

```bash
rga 'quarterly revenue' docs/        # search a phrase across mixed file types
rga -i 'invoice' contracts/          # case-insensitive, like rg
rga -l 'data processing agreement'   # files-with-matches only
rga -C 2 'termination clause'        # context lines, like rg
```

Caching and adapters:

```bash
rga --rga-list-adapters              # show available format adapters
rga --rga-adapters=poppler,zip 'x' . # restrict to specific adapters
rga --rga-no-cache 'x' .             # bypass the extracted-text cache
```

The first search over a corpus extracts and caches text (can be slow); repeat
searches over the same files are fast because they hit the cache.

## pdftotext — extract a PDF to a stream and pipe to rg

```bash
pdftotext report.pdf - | rg -n 'net income'    # '-' sends text to stdout
pdftotext -layout report.pdf - | rg 'Total'    # -layout preserves columns
```

Good when you want full control of the extracted text or rga isn't installed.

## pandoc — convert documents to a searchable/structured format

```bash
pandoc spec.docx -t markdown -o spec.md        # docx -> Markdown
pandoc notes.docx -t plain | rg 'deadline'     # to plain text, then grep
pandoc README.md -t gfm -o README.gfm.md       # normalize Markdown flavors
```

## When to reach past rga

Use `rga` for fast "find the phrase" across many files. Switch to **`pandoc`**
when you need the document's **structure** (headings, tables, lists) preserved
for downstream parsing or reformatting, and **`pdftotext -layout`** when column
or table **layout** matters for accurate extraction.
