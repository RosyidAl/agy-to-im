"""Tests for Markdown → Telegram HTML rendering (formatting quality + validity)."""
from __future__ import annotations

from html.parser import HTMLParser

import pytest

from src.telegram import (
    balance_html_chunks,
    html_to_plain,
    markdown_to_telegram_html,
)

_ALLOWED = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre",
            "blockquote", "tg-spoiler", "a", "span", "tg-emoji"}


class _Validator(HTMLParser):
    """Mimics Telegram's strict HTML parser: allowed tags + proper nesting."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):  # type: ignore[override]
        if tag not in _ALLOWED:
            self.errors.append(f"unsupported <{tag}>")
        if tag == "a" and not dict(attrs).get("href"):
            self.errors.append("<a> without href")
        self.stack.append(tag)

    def handle_endtag(self, tag):  # type: ignore[override]
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"bad close </{tag}> (stack={self.stack})")
        else:
            self.stack.pop()


def assert_valid(html_text: str) -> None:
    v = _Validator()
    v.feed(html_text)
    v.close()
    assert not v.errors, v.errors
    assert not v.stack, f"unclosed: {v.stack}"


# ── Regression: real reply (step 169) produced inverted bold ─────────────

def test_header_with_emoji_and_bold_does_not_shift_bold_pairs() -> None:
    md = (
        "### 📅 **Jadwal UTS Kelas A**\n\n"
        "Mulai hari **Selasa, 13 Oktober** dan selesai **Senin, 19 Oktober**."
    )
    out = markdown_to_telegram_html(md)
    assert_valid(out)
    assert "<b>📅 Jadwal UTS Kelas A</b>" in out
    assert "<b>Selasa, 13 Oktober</b>" in out
    assert "<b>Senin, 19 Oktober</b>" in out
    assert "**" not in out


def test_header_without_emoji_gets_icon() -> None:
    out = markdown_to_telegram_html("## Ringkasan")
    assert out == "📌 <b>Ringkasan</b>"


def test_bold_does_not_span_lines() -> None:
    out = markdown_to_telegram_html("a ** b\nc ** d")
    assert "<b>" not in out
    assert_valid(out)


# ── Tables ───────────────────────────────────────────────────────────────

def test_narrow_table_renders_as_aligned_pre() -> None:
    md = "| x | f(x) |\n|---|---|\n| 1 | 0.5 |\n| 2 | 1.25 |"
    out = markdown_to_telegram_html(md)
    assert_valid(out)
    assert out.startswith("<pre>") and out.endswith("</pre>")
    assert "|" not in out
    assert "─" in out  # header underline
    assert "f(x)" in out and "1.25" in out
    assert "---" not in out


def test_wide_table_renders_as_cards() -> None:
    md = (
        "| Hari & Tanggal | Mata Kuliah | Sesi | Ruangan |\n"
        "| :--- | :--- | :---: | :--- |\n"
        "| **Selasa, 13 Okt 2026** | 1. PBO<br>2. Basis Data | Sesi 1 – 2 | B4-11 |\n"
    )
    out = markdown_to_telegram_html(md)
    assert_valid(out)
    assert "▸ <b>Selasa, 13 Okt 2026</b>" in out
    assert "Mata Kuliah: 1. PBO; 2. Basis Data" in out
    assert "Ruangan: B4-11" in out
    assert "|" not in out
    assert "&lt;br" not in out


# ── Alerts, quotes, spoilers ─────────────────────────────────────────────

@pytest.mark.parametrize("kind,icon,label", [
    ("NOTE", "ℹ️", "Catatan"),
    ("TIP", "💡", "Tips"),
    ("IMPORTANT", "❗", "Penting"),
    ("WARNING", "⚠️", "Peringatan"),
    ("CAUTION", "🛑", "Hati-hati"),
])
def test_github_alert_becomes_labeled_blockquote(kind: str, icon: str, label: str) -> None:
    out = markdown_to_telegram_html(f"> [!{kind}]\n> Isi **penting** di sini.")
    assert_valid(out)
    assert out.startswith(f"<blockquote>{icon} <b>{label}</b>\n")
    assert "Isi <b>penting</b> di sini." in out
    assert "[!" not in out


def test_long_blockquote_is_expandable() -> None:
    md = "\n".join(f"> baris {i}" for i in range(10))
    out = markdown_to_telegram_html(md)
    assert_valid(out)
    assert out.startswith("<blockquote expandable>")


def test_spoiler_syntax() -> None:
    out = markdown_to_telegram_html("Jawabannya ||42||")
    assert out == "Jawabannya <tg-spoiler>42</tg-spoiler>"


# ── Math / LaTeX ─────────────────────────────────────────────────────────

def test_inline_latex_becomes_unicode() -> None:
    out = markdown_to_telegram_html(r"Akar $x_1 \approx \mathbf{-1.6077}$ pada $x \in [-3, 2]$, $x^2 \to \infty$")
    assert_valid(out)
    assert "$" not in out
    assert "x₁ ≈ -1.6077" in out
    assert "x ∈ [-3, 2]" in out
    assert "x² → ∞" in out


def test_dollar_amounts_are_not_treated_as_math() -> None:
    out = markdown_to_telegram_html("Harga $5 dan $10 saja")
    assert out == "Harga $5 dan $10 saja"


# ── Links, images, paths ─────────────────────────────────────────────────

def test_file_link_shows_basename_only() -> None:
    out = markdown_to_telegram_html("Lihat [`plot.png`](file:///home/u/chats/1/plot.png)")
    assert_valid(out)
    assert "/home/u" not in out
    assert "📄 <code>plot.png</code>" in out


def test_image_markdown_is_replaced_with_caption() -> None:
    out = markdown_to_telegram_html("![Visualisasi Fungsi](/home/u/chats/1/plot.png)")
    assert out == "🖼️ <i>Visualisasi Fungsi</i>"


def test_http_link_kept_and_underscores_in_url_not_italicized() -> None:
    out = markdown_to_telegram_html("[docs](https://ex.com/a_b_c_d) dan _miring_")
    assert_valid(out)
    assert '<a href="https://ex.com/a_b_c_d">docs</a>' in out
    assert "<i>miring</i>" in out


# ── Lists, misc ──────────────────────────────────────────────────────────

def test_checkboxes_and_nested_bullets() -> None:
    out = markdown_to_telegram_html("- [ ] belum\n- [x] sudah\n- utama\n  - anak")
    assert "☐ belum" in out
    assert "✅ sudah" in out
    assert "• utama" in out
    assert "  ◦ anak" in out


def test_raw_br_becomes_newline() -> None:
    assert markdown_to_telegram_html("a<br>b<br/>c") == "a\nb\nc"


def test_mermaid_block_is_labeled() -> None:
    out = markdown_to_telegram_html("```mermaid\nflowchart LR\n A-->B\n```")
    assert_valid(out)
    assert out.startswith("📊 <i>Diagram (mermaid)</i>\n<pre>")
    assert "A--&gt;B" in out


def test_code_block_content_untouched() -> None:
    out = markdown_to_telegram_html("```python\nx = a**2 * b**2  # _not italic_\n```")
    assert_valid(out)
    assert "a**2 * b**2" in out
    assert "<i>" not in out


def test_unclosed_code_fence_is_closed() -> None:
    out = markdown_to_telegram_html("Contoh:\n```python\nprint('hi')")
    assert_valid(out)
    assert "print(&#x27;hi&#x27;)" in out or "print('hi')" in out
    assert "```" not in out


# ── Chunk balancing & plain fallback ─────────────────────────────────────

def test_balance_reopens_tags_with_attributes() -> None:
    chunks = ['<a href="https://x.y">part one', ' part two</a>']
    out = balance_html_chunks(chunks)
    assert out[0].endswith("</a>")
    assert out[1].startswith('<a href="https://x.y">')
    for c in out:
        assert_valid(c)


def test_html_to_plain_strips_tags_and_unescapes() -> None:
    assert html_to_plain("<b>a &amp; b</b> <code>x&lt;y</code>") == "a & b x<y"


def test_real_world_reply_is_valid_and_has_no_raw_markers() -> None:
    md = (
        "Grafik untuk fungsi **$f(x) = \\sin(2x) - e^{x-1}$** berhasil! 📊\n\n"
        "![Visualisasi](/home/r/plot.png)\n\n---\n\n"
        "### 📂 File:\n"
        "* **PNG:** [fungsi_plot.png](file:///home/r/fungsi_plot.png)\n\n"
        "1. **Akar ($f(x) = 0$):**\n   * $x_1 \\approx \\mathbf{-1.6077}$\n\n"
        "> [!NOTE]\n> *Catatan:* binary `Utl<x>`.\n"
    )
    out = markdown_to_telegram_html(md)
    assert_valid(out)
    for raw in ("**", "$", "[!NOTE]", "file://", "![", "---"):
        assert raw not in out, raw
