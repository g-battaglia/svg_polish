# CLI Reference

## Usage

```
svg-polish [INPUT.SVG [OUTPUT.SVG]] [OPTIONS]
svg-polish -i INPUT.SVG -o OUTPUT.SVG [OPTIONS]
```

If input/output files are not specified, stdin/stdout are used.
If files have a `.svgz` extension, gzip-compressed SVG is assumed.

## Input / Output

| Option | Description |
|--------|-------------|
| `-i INPUT.SVG` | Input SVG file |
| `-o OUTPUT.SVG` | Output SVG file |
| `-q`, `--quiet` | Suppress non-error output |
| `-v`, `--verbose` | Show detailed optimization statistics |
| `--version` | Show version and exit |
| `-h`, `--help` | Show help and exit |

## Optimization Options

| Option | Description | Default |
|--------|-------------|---------|
| `--set-precision=NUM` | Number of significant digits for coordinates | 5 |
| `--set-c-precision=NUM` | Significant digits for control points | same as `--set-precision` |
| `--disable-simplify-colors` | Don't convert colors to short `#RGB` format | colors simplified |
| `--disable-style-to-xml` | Don't convert inline styles to XML attributes | styles converted |
| `--disable-group-collapsing` | Don't collapse redundant `<g>` elements | groups collapsed |
| `--create-groups` | Create `<g>` elements for runs of elements with identical attributes | disabled |
| `--keep-editor-data` | Keep Inkscape, Sodipodi, Adobe, Sketch metadata | removed |
| `--keep-unreferenced-defs` | Keep unused elements in `<defs>` | removed |
| `--renderer-workaround` | Work around renderer bugs (librsvg) | enabled |
| `--no-renderer-workaround` | Disable renderer workarounds | |

## Document Options

| Option | Description | Default |
|--------|-------------|---------|
| `--strip-xml-prolog` | Remove `<?xml ?>` declaration | kept |
| `--remove-titles` | Remove `<title>` elements | kept |
| `--remove-descriptions` | Remove `<desc>` elements | kept |
| `--remove-metadata` | Remove `<metadata>` elements | kept |
| `--remove-descriptive-elements` | Remove `<title>`, `<desc>`, and `<metadata>` | kept |
| `--enable-comment-stripping` | Remove all XML comments | kept |
| `--disable-embed-rasters` | Don't embed raster images as base64 | embedded |
| `--enable-viewboxing` | Add `viewBox`, change width/height to 100% | disabled |

## Output Formatting

| Option | Description | Default |
|--------|-------------|---------|
| `--indent=TYPE` | Indentation: `none`, `space`, or `tab` | `space` |
| `--nindent=NUM` | Indentation depth (number of spaces/tabs) | 1 |
| `--no-line-breaks` | No line breaks (also disables indentation) | line breaks on |
| `--strip-xml-space` | Strip `xml:space="preserve"` from root | kept |

## ID Options

| Option | Description | Default |
|--------|-------------|---------|
| `--enable-id-stripping` | Remove all unreferenced IDs | disabled |
| `--shorten-ids` | Shorten IDs to minimal length | disabled |
| `--shorten-ids-prefix=PREFIX` | Add prefix to shortened IDs | none |
| `--protect-ids-noninkscape` | Don't remove IDs not ending with a digit | disabled |
| `--protect-ids-list=LIST` | Comma-separated list of IDs to protect | none |
| `--protect-ids-prefix=PREFIX` | Don't remove IDs starting with this prefix | none |

## Compatibility

| Option | Description | Default |
|--------|-------------|---------|
| `--error-on-flowtext` | Exit with error on non-standard flowing text | warn only |

## Examples

### Basic optimization

```bash
svg-polish -i logo.svg -o logo.min.svg
```

### Maximum compression

```bash
svg-polish -i input.svg -o output.svg \
  --enable-viewboxing \
  --enable-id-stripping \
  --enable-comment-stripping \
  --shorten-ids \
  --indent=none \
  --no-line-breaks \
  --strip-xml-prolog \
  --remove-descriptive-elements
```

### Pipeline usage

```bash
# Optimize all SVGs in a directory
for f in icons/*.svg; do
  svg-polish -i "$f" -o "dist/$(basename "$f")"
done

# Pipe through other tools
curl -s https://example.com/image.svg | svg-polish > optimized.svg
```

### Compressed SVGZ

```bash
svg-polish -i input.svg -o output.svgz
```

### Keep editor metadata

```bash
svg-polish -i input.svg -o output.svg --keep-editor-data
```

### Custom precision

```bash
# Lower precision for smaller files (may affect quality)
svg-polish -i input.svg -o output.svg --set-precision=3

# Higher precision for accuracy
svg-polish -i input.svg -o output.svg --set-precision=8
```

### Verbose output

```bash
svg-polish -i input.svg -o output.svg -v
```

This prints detailed statistics:

```
Number of elements removed: 12
Number of attributes removed: 45
Number of bytes saved in path data: 234
...
```
