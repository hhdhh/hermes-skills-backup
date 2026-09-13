#!/usr/bin/env python3
"""
TokenJuice — OpenHuman-inspired content compression module for Huihui
Based on: tinyhumansai/openhuman TokenJuice tech

Core responsibilities:
1. HTML → Markdown conversion
2. URL deduplication and shortening
3. Remove ads/navigation/noise
4. Chunk text into ≤3000 token pieces (CJK-aware)
5. Preserve semantic structure

Usage:
    python3 token_juice.py --input path_or_url [--output output.md] [--chunk-size 3000]
"""

import re
import sys
import os
import html
from urllib.parse import urlparse, urljoin
from typing import Optional

# ─── Configuration ───────────────────────────────────────────────────────────

MAX_CHUNK_TOKENS = 3000
CHARS_PER_TOKEN = 4  # conservative estimate for CJK
MAX_CHUNK_CHARS = MAX_CHUNK_TOKENS * CHARS_PER_TOKEN

# Noise patterns to strip
NOISE_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'<style[^>]*>.*?</style>',
    r'<nav[^>]*>.*?</nav>',
    r'<footer[^>]*>.*?</footer>',
    r'<header[^>]*>.*?</header>',
    r'<aside[^>]*>.*?</aside>',
    r'<!--.*?-->',
    r'<noscript[^>]*>.*?</noscript>',
    r'<iframe[^>]*>.*?</iframe>',
]

# ─── HTML Cleaning ────────────────────────────────────────────────────────────

def clean_html(raw_html: str) -> str:
    """Remove noise elements (scripts, styles, nav, ads, etc.)"""
    text = raw_html
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    return text

def html_to_markdown(raw_html: str) -> str:
    """Convert cleaned HTML to markdown with CJK awareness"""
    text = clean_html(raw_html)
    
    # Handle code blocks first (preserve indentation)
    text = re.sub(r'<pre><code[^>]*>(.*?)</code></pre>', 
                  lambda m: '\n```\n' + html.unescape(m.group(1)) + '\n```\n', 
                  text, flags=re.DOTALL)
    text = re.sub(r'<code[^>]*>(.*?)</code>', 
                  lambda m: '`' + html.unescape(m.group(1)) + '`', text, flags=re.DOTALL)
    
    # Headers
    for i in range(6, 0, -1):
        text = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', 
                      lambda m: '\n' + '#' * i + ' ' + html.unescape(m.group(1)) + '\n', 
                      text, flags=re.DOTALL)
    
    # Bold and italic
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
    
    # Links
    text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                  lambda m: f'[{html.unescape(m.group(2))}]({m.group(1)})', text, flags=re.DOTALL)
    
    # Images
    text = re.sub(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>',
                  lambda m: f'![{html.unescape(m.group(2))}]({m.group(1)})', text)
    text = re.sub(r'<img[^>]*alt=["\']([^"\']*)["\'][^>]*src=["\']([^"\']+)["\'][^>]*>',
                  lambda m: f'![{html.unescape(m.group(1))}]({m.group(2)})', text)
    text = re.sub(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', r'![](\1)', text)
    
    # Lists
    text = re.sub(r'<li[^>]*>(.*?)</li>', lambda m: '- ' + html.unescape(m.group(1)) + '\n', text, flags=re.DOTALL)
    text = re.sub(r'<ul[^>]*>', '\n', text)
    text = re.sub(r'</ul>', '\n', text)
    text = re.sub(r'<ol[^>]*>', '\n', text)
    text = re.sub(r'</ol>', '\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<div[^>]*>', '\n', text)
    text = re.sub(r'</div>', '\n', text)
    
    # Tables
    text = re.sub(r'<table[^>]*>', '\n<table>', text)
    text = re.sub(r'</table>', '</table>\n', text)
    text = re.sub(r'<th[^>]*>', '|', text)
    text = re.sub(r'</th>', '', text)
    text = re.sub(r'<td[^>]*>', '|', text)
    text = re.sub(r'</td>', '', text)
    
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace per line but preserve structure
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    text = '\n'.join(lines)
    
    return text.strip()

# ─── URL Processing ───────────────────────────────────────────────────────────

def compress_url(url: str, max_len: int = 60) -> str:
    """Shorten long URLs while preserving path identity"""
    if len(url) <= max_len:
        return url
    
    parsed = urlparse(url)
    # Keep scheme and netloc, truncate path
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path
    
    if len(base) + len(path) > max_len:
        # Truncate path, keep last meaningful segment
        segments = [s for s in path.split('/') if s]
        if segments:
            truncated = '/' + '/'.join(segments[-2:]) if len(segments) > 1 else '/' + segments[-1]
            result = base + truncated
            if len(result) > max_len:
                return base[:max_len-3] + '...'
            return result
    return url[:max_len-3] + '...' if len(url) > max_len else url

def deduplicate_urls(text: str) -> str:
    """Find and replace duplicate URLs with reference notation"""
    urls = re.findall(r'https?://[^\s\)\"\']+', text)
    url_counts = {}
    
    for url in urls:
        if url not in url_counts:
            url_counts[url] = 0
        url_counts[url] += 1
    
    # Replace duplicates with compressed form
    seen = {}
    for url, count in url_counts.items():
        if count > 1:
            compressed = compress_url(url)
            # Keep first occurrence, reference rest
            placeholder = f"[{compressed}]"
            first_occurrence = True
            def replace_url(m):
                nonlocal first_occurrence
                if first_occurrence:
                    first_occurrence = False
                    return m.group(0)
                return placeholder
            text = re.sub(re.escape(url), replace_url, text)
        elif len(url) > 60:
            text = text.replace(url, compress_url(url))
    
    return text

# ─── CJK-Aware Chunking ───────────────────────────────────────────────────────

def is_cjk_char(char: str) -> bool:
    """Check if character is CJK"""
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF or   # CJK Unified Ideographs
        0x3400 <= code <= 0x4DBF or   # CJK Extension A
        0xF900 <= code <= 0xFAFF or   # CJK Compatibility Ideographs
        0x3000 <= code <= 0x303F or   # CJK Symbols
        0xFF00 <= code <= 0xFFEF      # Halfwidth and Fullwidth Forms
    )

def grapheme_length(text: str) -> int:
    """Count characters (graphemes) CJK-aware — CJK chars count as 1, not 2"""
    # For token estimation, we count grapheme clusters
    # CJK characters are counted individually (1 per char)
    # Latin characters average ~4 per token
    count = 0
    i = 0
    while i < len(text):
        if is_cjk_char(text[i]):
            count += 1
            i += 1
        else:
            # Latin sequence — count as ~0.25 per char (4 per token)
            j = i
            while j < len(text) and not is_cjk_char(text[j]):
                j += 1
            count += (j - i) / CHARS_PER_TOKEN
            i = j
    return int(count)

def chunk_by_tokens(text: str, max_tokens: int = MAX_CHUNK_TOKENS) -> list[str]:
    """
    Split text into chunks of ≤max_tokens.
    Split on paragraph boundaries when possible to preserve semantic units.
    CJK-aware: counts graphemes, not bytes.
    """
    # Split into paragraphs first
    paragraphs = re.split(r'\n{2,}', text)
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for para in paragraphs:
        if not para.strip():
            continue
        
        para_tokens = grapheme_length(para)
        
        if para_tokens > max_tokens:
            # Single paragraph exceeds limit — split by sentence
            sentences = re.split(r'(?<=[。！？.!?])\s*', para)
            for sentence in sentences:
                if not sentence.strip():
                    continue
                sent_tokens = grapheme_length(sentence)
                if sent_tokens > max_tokens:
                    # Still too long — hard split at max_chars
                    while sentence:
                        chunk_text = sentence[:MAX_CHUNK_CHARS]
                        chunks.append(chunk_text.strip())
                        sentence = sentence[MAX_CHUNK_CHARS:]
                elif current_tokens + sent_tokens > max_tokens:
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                    current_chunk = [sentence]
                    current_tokens = sent_tokens
                else:
                    current_chunk.append(sentence)
                    current_tokens += sent_tokens
        elif current_tokens + para_tokens > max_tokens:
            # Would exceed limit — save current and start new
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            current_chunk = [para]
            current_tokens = para_tokens
        else:
            current_chunk.append(para)
            current_tokens += para_tokens
    
    # Flush remaining
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return [c.strip() for c in chunks if c.strip()]

# ─── Main Processor ───────────────────────────────────────────────────────────

def process_content(raw: str, source_type: str = "text") -> dict:
    """
    Process raw content through TokenJuice pipeline.
    
    Returns:
        {
            "markdown": str,          # Clean markdown
            "chunks": list[str],      # Token-chunked segments
            "stats": {
                "original_chars": int,
                "final_chars": int,
                "compression_ratio": float,
                "num_chunks": int,
                "total_tokens_estimate": int
            }
        }
    """
    # Convert HTML if needed
    if source_type == "html":
        text = html_to_markdown(raw)
    else:
        text = raw
    
    # Remove extra whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\r\n', '\n', text)
    
    # Deduplicate URLs
    text = deduplicate_urls(text)
    
    # Count original length
    original_chars = len(raw)
    final_chars = len(text)
    
    # Chunk
    chunks = chunk_by_tokens(text)
    total_tokens = sum(grapheme_length(c) for c in chunks)
    
    return {
        "markdown": text,
        "chunks": chunks,
        "stats": {
            "original_chars": original_chars,
            "final_chars": final_chars,
            "compression_ratio": (original_chars - final_chars) / original_chars if original_chars else 0,
            "num_chunks": len(chunks),
            "total_tokens_estimate": total_tokens
        }
    }

def process_file(filepath: str) -> dict:
    """Process a local file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    
    # Detect HTML by extension or content
    is_html = filepath.endswith('.html') or filepath.endswith('.htm')
    is_markdown = filepath.endswith('.md')
    
    source_type = "html" if is_html else "markdown" if is_markdown else "text"
    
    return process_content(raw, source_type)

def process_url(url: str) -> dict:
    """Fetch and process a URL (requires requests library)"""
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests library required for URL processing: pip install requests")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; HuihuiBot/1.0; +https://huihui.ai)',
        'Accept': 'text/html,application/xhtml+xml'
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    return process_content(response.text, source_type="html")

# ─── CLI Interface ────────────────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='TokenJuice — Content compression for AI agents')
    parser.add_argument('--input', '-i', required=True, help='File path or URL to process')
    parser.add_argument('--output', '-o', help='Output markdown file (default: stdout)')
    parser.add_argument('--chunks', '-c', action='store_true', help='Output chunks instead of full text')
    parser.add_argument('--stats', '-s', action='store_true', help='Show compression stats')
    parser.add_argument('--chunk-size', type=int, default=MAX_CHUNK_TOKENS, help=f'Max tokens per chunk (default: {MAX_CHUNK_TOKENS})')
    
    args = parser.parse_args()
    
    # Process
    if args.input.startswith('http://') or args.input.startswith('https://'):
        result = process_url(args.input)
    elif os.path.isfile(args.input):
        result = process_file(args.input)
    else:
        print(f"Error: {args.input} is not a valid file or URL", file=sys.stderr)
        sys.exit(1)
    
    # Output
    output = '\n\n---\n\n'.join(result['chunks']) if args.chunks else result['markdown']
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Saved to {args.output}")
    else:
        print(output)
    
    if args.stats:
        stats = result['stats']
        print(f"\n📊 TokenJuice Stats:", file=sys.stderr)
        print(f"  Original: {stats['original_chars']:,} chars", file=sys.stderr)
        print(f"  Final: {stats['final_chars']:,} chars", file=sys.stderr)
        print(f"  Compression: {stats['compression_ratio']:.1%}", file=sys.stderr)
        print(f"  Chunks: {stats['num_chunks']}", file=sys.stderr)
        print(f"  Est. tokens: {stats['total_tokens_estimate']:,}", file=sys.stderr)

if __name__ == '__main__':
    main()