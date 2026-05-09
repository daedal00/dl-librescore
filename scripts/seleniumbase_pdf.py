# /// script
# requires-python = ">=3.12"
# dependencies = ["seleniumbase>=4.27.0", "pillow", "reportlab", "requests", "cairosvg", "pypdf"]
# ///

"""
Download a MuseScore score as a high-quality PDF via browser automation.
Uses SeleniumBase UC (undetected-chrome) mode for anti-bot bypass.

Quality tiers (best → worst):
  1. Vector PDF  — SVG scores converted with cairosvg+pypdf (infinite zoom)
  2. ~259 DPI    — PNG scores embedded directly
  3. 72 DPI      — WebDriver element-screenshot fallback

Performance:
  - Image downloads run in parallel (8 workers) while the browser session
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

    status("Opening MuseScore with anti-bot bypass…")

    img_urls: list[str | None] = []
    fallback_shots: list[bytes | None] = []
    dl_futures: list[Future] = []
    cookies_list: list[dict] = []
    title = "score"

    executor = ThreadPoolExecutor(max_workers=8)

    # UC mode + headless2 (stealth headless) + xvfb (virtual display for CI).
    with SB(uc=True, xvfb=True, headless2=True, test=False) as sb:
        # UC mode: open with reconnect to bypass Cloudflare/anti-bot.
        sb.uc_open_with_reconnect(score_url, reconnect_time=4)

        status("Waiting for score to load…")
        try:
            sb.wait_for_element_present("meta[property='al:ios:url']", timeout=180)
        except Exception:
            current_title = sb.get_title()
            # Cloudflare still showing?
            if "Just a moment" in current_title:
                status("Cloudflare challenge detected, reconnecting…")
                sb.reconnect(5)
                sb.wait_for_element_present("meta[property='al:ios:url']", timeout=180)
            else:
                # One more reconnect attempt just in case
                sb.reconnect(3)
                try:
                    sb.wait_for_element_present("meta[property='al:ios:url']", timeout=60)
                except Exception as e:
                    status(f"Page title: {current_title}")
                    body_preview = sb.execute_script(
                        "return document.body?.innerText?.slice(0,500) || ''"
                    )
                    status(f"Body preview: {body_preview[:200]}")
                    raise TimeoutError("Timed out waiting for MuseScore page to load") from e

        # Brief pause for React hydration
        sb.sleep(1)

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
            page_count = sb.execute_script("""
                const scroller = document.querySelector('#jmuse-scroller-component');
                return scroller ? scroller.children.length : 0;
            """)
            if not page_count:
                raise RuntimeError("No score pages found")

        status(f"Collecting {page_count} page(s)…")

        for index in range(page_count):
            img_url: str | None = None
            for _ in range(15):
                img_url = sb.execute_script(f"""
                    (() => {{
                      const scroller = document.querySelector('#jmuse-scroller-component');
                      const page = scroller?.children?.[{index}];
                      page?.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                      const img = page?.querySelector('img[src*="score_"]');
                      if (!img) return null;
                      img.setAttribute('data-librescore-capture', '1');
                      return img.currentSrc || img.src || null;
                    }})()
                """)
                if img_url:
                    break
                sb.sleep(0.3)

            img_urls.append(img_url)

            # Fallback screenshot via WebDriver (CDP disabled so UC mode stays effective)
            sb.sleep(0.15)
            try:
                el = sb.find_element('img[data-librescore-capture="1"]', timeout=2)
                png_bytes = el.screenshot_as_png
                fallback_shots.append(png_bytes)
                # Clear the attribute so stale elements don't match again
                sb.execute_script("arguments[0].removeAttribute('data-librescore-capture')", el)
            except Exception:
                fallback_shots.append(None)

        # Grab cookies after all page interactions so auth tokens are included
        try:
            cookies_list = sb.get_cookies() or []
        except Exception:
            pass

        # Kick off parallel downloads while browser is still alive
        for url in img_urls:
            dl_futures.append(
                executor.submit(download_page, url, score_url, cookies_list)
            )

    # Collect download results
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

    # Reference page size in PDF points from the first screenshot
    ref_w, ref_h = 827.0, 1170.0
    for shot in fallback_shots:
        if shot:
            w, h = Image.open(BytesIO(shot)).size
            ref_w, ref_h = float(w), float(h)
            break

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
                try:
                    png_data = cairosvg.svg2png(bytestring=data, scale=1.0)
                    pdf_pages.append(_raster_pdf_page(_pil_from_bytes(png_data), ref_w, ref_h))
                    continue
                except Exception:
                    pass
            elif not is_svg:
                pdf_pages.append(_raster_pdf_page(_pil_from_bytes(data), ref_w, ref_h))
                continue

        if shot:
            pdf_pages.append(_raster_pdf_page(_pil_from_bytes(shot), ref_w, ref_h))
        else:
            raise RuntimeError(f"No image data for page {i}")

    if HAS_VECTOR:
        output_pdf.write_bytes(_merge_pdf_pages(pdf_pages))
    else:
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
