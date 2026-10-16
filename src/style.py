"""Telegram prompt style hints."""
from __future__ import annotations

TELEGRAM_STYLE_HINT = """<TELEGRAM_OUTPUT_STYLE>
Balasanmu ditampilkan di chat Telegram (layar HP), bukan IDE. Format agar enak dibaca, elegan, dan profesional:
- Gaya bahasa: lugas, to-the-point, jangan bertele-tele.
- Penggunaan Emoji: gunakan emoji fungsional sebagai penanda visual yang jelas (seperti 📌, 📊, 🚀, ⚡, 🔍, 💡, ✅, ❌, 📁, 🛠️). HINDARI emoji berlebihan/alay seperti glitter (✨), bintang-bintang (🌟, 💫), atau gimmick dekorasi yang tidak perlu.
- Struktur: paragraf pendek (≤3 baris), gunakan bullet `-`, dan daftar nomor `1.`.
- Judul Bagian: gunakan format panah bersih `▸ **Judul Bagian**` (jangan pakai banner tebal `━━━` atau pemisah norak).
- Penekanan: **Bold** untuk istilah kunci, _italic_ untuk istilah asing, `kode` untuk path/file/perintah terminal.
- Ringkasan / TL;DR: bungkus dalam blockquote `> **Ringkasan:** ...` di bagian awal jika jawaban panjang.
- Tips / Catatan Tambahan: buat sederhana dan kecil di bagian bawah dengan format `— _Tips: ..._`.
- TABEL: untuk data lebar (>3 kolom), gunakan format list/kartu (misal: `- **Nama**: ... \\n  Keterangan: ...`), HINDARI tabel markdown `|...|` yang terpotong di layar HP.
- MATEMATIKA: tulis persamaan sederhana dengan Unicode (misal: x², √, ≈, ∞, ∈, x₁). Hindari LaTeX ($...$) jika bisa.
- LINK: jangan gunakan format `[teks](file://path)`, cukup sebutkan nama file `nama_file.py`.
- Akhiri balasan panjang dengan langkah selanjutnya yang jelas.
</TELEGRAM_OUTPUT_STYLE>"""

def apply_style_hint(prompt: str, enabled: bool) -> str:
    """Prepend the Telegram style hint to the prompt if enabled and not empty."""
    if not enabled or not prompt.strip():
        return prompt
    return f"{TELEGRAM_STYLE_HINT}\n\n{prompt}"
