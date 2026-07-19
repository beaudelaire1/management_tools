"""Minimal deterministic PDF writer with no external dependency.

Financial documents must be reproducible: the same invoice data always yields
byte-identical output (spec invariant 11.2). Streams are left uncompressed and
no generation timestamp is embedded, so rendering is a pure function of its
input and tests can assert on the raw bytes. Text uses the built-in Helvetica
fonts with WinAnsi (cp1252) encoding, which covers French mandatory mentions.
"""

from dataclasses import dataclass, field

A4_WIDTH = 595
A4_HEIGHT = 842

_FONT_REGULAR = "F1"
_FONT_BOLD = "F2"


@dataclass(frozen=True)
class _TextOp:
    x: float
    y: float
    size: float
    text: str
    bold: bool


@dataclass
class PdfPage:
    ops: list[_TextOp] = field(default_factory=list)

    def text(self, x: float, y: float, text: str, *, size: float = 10.0, bold: bool = False) -> None:
        self.ops.append(_TextOp(x=x, y=y, size=size, text=text, bold=bold))


def _escape(text: str) -> bytes:
    encoded = text.encode("cp1252", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _number(value: float) -> str:
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return formatted or "0"


class PdfWriter:
    """Accumulates pages of positioned text and renders a valid PDF 1.4 file."""

    def __init__(self) -> None:
        self.pages: list[PdfPage] = []

    def add_page(self) -> PdfPage:
        page = PdfPage()
        self.pages.append(page)
        return page

    def render(self) -> bytes:
        if not self.pages:
            self.add_page()
        # Object layout: 1 catalog, 2 pages root, 3 regular font, 4 bold font,
        # then one page object and one content stream object per page.
        objects: list[bytes] = []
        page_object_numbers = [5 + index * 2 for index in range(len(self.pages))]
        kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(
            f"<< /Type /Pages /Kids [{kids}] /Count {len(self.pages)} >>".encode("ascii")
        )
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        for index, page in enumerate(self.pages):
            content = self._content_stream(page)
            page_number = page_object_numbers[index]
            objects.append(
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {A4_WIDTH} {A4_HEIGHT}] "
                    f"/Resources << /Font << /{_FONT_REGULAR} 3 0 R /{_FONT_BOLD} 4 0 R >> >> "
                    f"/Contents {page_number + 1} 0 R >>"
                ).encode("ascii")
            )
            objects.append(
                b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
            )

        output = bytearray(b"%PDF-1.4\n")
        offsets: list[int] = []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        xref_offset = len(output)
        output += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
        output += b"0000000000 65535 f \n"
        for offset in offsets:
            output += f"{offset:010d} 00000 n \n".encode("ascii")
        output += (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
        return bytes(output)

    @staticmethod
    def _content_stream(page: PdfPage) -> bytes:
        parts: list[bytes] = []
        for op in page.ops:
            font = _FONT_BOLD if op.bold else _FONT_REGULAR
            parts.append(
                f"BT /{font} {_number(op.size)} Tf 1 0 0 1 {_number(op.x)} {_number(op.y)} Tm (".encode("ascii")
                + _escape(op.text)
                + b") Tj ET"
            )
        return b"\n".join(parts)
