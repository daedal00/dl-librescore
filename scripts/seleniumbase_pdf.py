# /// script
# requires-python = ">=3.12"
# dependencies = ["seleniumbase", "pillow", "reportlab", "requests", "cairosvg", "pypdf"]
# ///

"""
Download a MuseScore score as a high-quality PDF via browser automation.

Quality tiers (best → worst):
  1. Vector PDF  — SVG scores converted with cairosvg+pypdf (infinite zoom)
  2. ~259 DPI    — PNG scores embedded directly
  3. 72 DPI      — screenshot fallback when download fails

Performance:
  - Image downloads run in parallel (4 workers) while the browser session
    is still active so network latency overlaps with browser operations.
  - Screenshots are taken only for pages whose download failed.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import requests as req_lib
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from seleniumbase import SB

try:
    import cairosvg
    from pypdf import PdfReader, PdfWriter
    HAS_VECTOR = True
except Exception:
    HAS_VECTOR = False


def status(msg: str) -> None:
    print(msg, flush=True)


def wait_for_score(sb, timeout: int = 180) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if (
                sb.is_element_present("meta[property='al:ios:url']")
                and "Just a moment" not in sb.get_title()
            ):
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("Timed out waiting for MuseScore page to load")


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _session(score_url: str, cookies: list[dict]) -> req_lib.Session:
    s = req_lib.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": score_url,
        "Accept": "image/svg+xml,image/png,image/*",
    })
    for c in cookies:
        s.cookies.set(c["name"], c["value"])
    return s


def _is_svg(data: bytes, url: str) -> bool:
    return url.lower().split("?")[0].endswith(".svg") or data[:500].lstrip().startswith(b"<svg")


def download_page(url: str | None, score_url: str, cookies: list[dict]) -> tuple[bytes, bool] | None:
    """Fetch image bytes; return (data, is_svg) or None on any failure."""
    if not url:
        return None
    try:
        r = _session(score_url, cookies).get(url, timeout=30)
        if not r.ok:
            return None
        data = r.content
        return (data, _is_svg(data, url))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _pil_from_bytes(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data)).convert("RGB")


def _raster_pdf_page(img: Image.Image, w_pts: float, h_pts: float) -> bytes:
    """Wrap a PIL image in a single-page reportlab PDF."""
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.setPageSize((w_pts, h_pts))
    c.drawImage(ImageReader(img), 0, 0, width=w_pts, height=h_pts)
    c.showPage()
    c.save()
    return buf.getvalue()


def _vector_pdf_page(svg_data: bytes) -> bytes | None:
    """Convert SVG bytes to a single-page vector PDF; return None on failure."""
    try:
        return cairosvg.svg2pdf(bytestring=svg_data)
    except Exception:
        return None


def _merge_pdf_pages(pages: list[bytes]) -> bytes:
    w = PdfWriter()
    for pb in pages:
        w.add_page(PdfReader(BytesIO(pb)).pages[0])
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: seleniumbase_pdf.py <score_url> <output_pdf>", file=sys.stderr)
        return 2

    score_url = sys.argv[1]
    output_pdf = Path(sys.argv[2]).resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    status("Opening MuseScore in SeleniumBase CDP mode…")

    img_urls: list[str | None] = []
    fallback_shots: list[bytes | None] = []   # 72-DPI screenshots, taken per-page
    dl_futures: list[Future] = []
    cookies_list: list[dict] = []
    title = "score"

    executor = ThreadPoolExecutor(max_workers=4)

    with SB(uc=True, xvfb=True, headless=True, test=False) as sb:
        sb.activate_cdp_mode(score_url)
        wait_for_score(sb)

        status("Loading score pages…")
        title = sb.execute_script(
            "return document.querySelector(\"meta[property='og:title']\")?.content"
            " || document.title || 'score'"
        )
        page_count = int(
            sb.execute_script(
                "return window.UGAPP?.store?.page?.data?.score?.pages_count || 0"
            ) or 0
        )

        if not page_count:
            raise RuntimeError("No score pages found")

        status(f"Collecting {page_count} page(s)…")

        for index in range(page_count):
            # Scroll to each page progressively (top → bottom). React's virtual
            # list loads a page's img when it enters the viewport; scrolling back
            # up after a full pre-scroll doesn't re-trigger IntersectionObserver
            # in headless mode, so no global pre-scroll is done here.
            # URL and marker attribute are read in one atomic JS call to avoid
            # a React re-render between find and read.
            img_url: str | None = None
            for _ in range(30):
                img_url = sb.execute_script(f"""
                    (() => {{
                      const scroller = document.querySelector('#jmuse-scroller-component');
                      const page = scroller?.children?.[{index}];
                      page?.scrollIntoView({{ block: 'center' }});
                      const img = page?.querySelector('img[src*="score_"]');
                      if (!img) return null;
                      img.setAttribute('data-librescore-capture', '1');
                      return img.currentSrc || img.src || null;
                    }})()
                """)
                if img_url:
                    break
                time.sleep(0.5)

            img_urls.append(img_url)

            # Screenshot taken immediately while the img is still marked.
            time.sleep(0.3)
            tmp_png = output_pdf.with_suffix(f".fallback{index}.png")
            try:
                sb.cdp.save_screenshot(
                    str(tmp_png.name), folder=str(tmp_png.parent),
                    selector='img[data-librescore-capture="1"]',
                )
                fallback_shots.append(tmp_png.read_bytes() if tmp_png.exists() else None)
                tmp_png.unlink(missing_ok=True)
            except Exception:
                fallback_shots.append(None)

        # Grab cookies after all page interactions so any auth tokens set
        # during scrolling are included.
        try:
            cookies_list = sb.get_cookies() or []
        except Exception:
            pass

        # Kick off parallel downloads now. They run while the browser is still
        # alive so any remaining browser cleanup overlaps with network I/O.
        for url in img_urls:
            dl_futures.append(
                executor.submit(download_page, url, score_url, cookies_list)
            )

    # Collect download results (most were already done during the browser session).
    status("Processing images…")
    dl_results: list[tuple[bytes, bool] | None] = [f.result() for f in dl_futures]
    executor.shutdown(wait=False)

    n_ok = sum(1 for r in dl_results if r is not None)
    if n_ok == 0:
        status(
            "Direct downloads failed — using screenshots (72 DPI). "
            + ("" if HAS_VECTOR else "Install cairosvg+pypdf+libcairo for better quality.")
        )
    elif n_ok < page_count:
        status(f"Downloaded {n_ok}/{page_count} pages; screenshots used for the rest.")

    # Reference page size in PDF points from the first screenshot (827×1170).
    ref_w, ref_h = 827.0, 1170.0
    if fallback_shots[0]:
        w, h = Image.open(BytesIO(fallback_shots[0])).size
        ref_w, ref_h = float(w), float(h)

    # Build per-page PDF buffers, then merge.
    status("Writing PDF…")
    pdf_pages: list[bytes] = []

    for i, (result, shot) in enumerate(zip(dl_results, fallback_shots)):
        if result is not None:
            data, is_svg = result
            if is_svg and HAS_VECTOR:
                page = _vector_pdf_page(data)
                if page:
                    pdf_pages.append(page)
                    continue
                # cairosvg failed on this specific SVG — rasterise at natural resolution
                try:
                    png_data = cairosvg.svg2png(bytestring=data, scale=1.0)
                    pdf_pages.append(_raster_pdf_page(_pil_from_bytes(png_data), ref_w, ref_h))
                    continue
                except Exception:
                    pass
            elif not is_svg:
                pdf_pages.append(_raster_pdf_page(_pil_from_bytes(data), ref_w, ref_h))
                continue

        # Fallback to screenshot for this page.
        if shot:
            pdf_pages.append(_raster_pdf_page(_pil_from_bytes(shot), ref_w, ref_h))
        else:
            raise RuntimeError(f"No image data for page {i}")

    if HAS_VECTOR:
        output_pdf.write_bytes(_merge_pdf_pages(pdf_pages))
    else:
        # pypdf unavailable: write a reportlab PDF by re-reading each raster page.
        # Each element of pdf_pages is already a single-page reportlab PDF whose
        # sole image we need to extract.  Since we built them ourselves above we
        # can reconstruct from fallback_shots directly.
        pdf = canvas.Canvas(str(output_pdf))
        for shot in fallback_shots:
            if shot:
                img = _pil_from_bytes(shot)
                pdf.setPageSize((ref_w, ref_h))
                pdf.drawImage(ImageReader(img), 0, 0, width=ref_w, height=ref_h)
                pdf.showPage()
        pdf.save()

    file_name = re.sub(r"[\s<>:{}\"/\\|?*~.\x00-\x1f]+", "_", title).strip("_") or "score"
    print(json.dumps({
        "title": title,
        "fileName": file_name,
        "pageCount": len(pdf_pages),
    }), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
