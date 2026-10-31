from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "data"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
LOG = logging.getLogger("qrcode_mirror")

# Detecta QR codes em img, canvas, svg e containers com identificadores
# relacionados a QR. O seletor automatico e reavaliado continuamente.
AUTO_DETECT_JS = r"""
() => {
  const visible = el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width >= 45 && r.height >= 45 &&
      r.width < innerWidth * 0.99 && r.height < innerHeight * 0.99 &&
      s.display !== 'none' && s.visibility !== 'hidden' &&
      Number(s.opacity) > 0 && r.bottom > 0 && r.right > 0 &&
      r.top < innerHeight && r.left < innerWidth;
  };

  const nodes = [...document.querySelectorAll(
    'img, canvas, svg, [style*="background"], ' +
    '[class*="qr" i], [id*="qr" i], [data-testid*="qr" i], ' +
    '[aria-label*="qr" i], [alt*="qr" i]'
  )];

  const scored = nodes.filter(visible).map(el => {
    const r = el.getBoundingClientRect();
    const tag = el.tagName.toLowerCase();
    const meta = [
      el.id,
      typeof el.className === 'string' ? el.className : '',
      el.getAttribute('alt'),
      el.getAttribute('title'),
      el.getAttribute('aria-label'),
      el.getAttribute('src'),
      el.getAttribute('data-testid')
    ].join(' ').toLowerCase();

    const ratio = Math.min(r.width, r.height) / Math.max(r.width, r.height);
    let score = 0;

    if (/qr.?code|qrcode|pix.?qr|qr-pix|codigo.?qr/.test(meta)) score += 140;
    if (tag === 'canvas') score += 28;
    if (tag === 'svg') score += 22;
    if (tag === 'img') score += 20;
    if (ratio > 0.78) score += 25;
    else if (ratio > 0.55) score += 8;
    else score -= 30;
    if (r.width >= 100 && r.height >= 100) score += 10;
    if (r.width >= 180 && r.height >= 180) score += 10;
    if (r.width > innerWidth * .85 || r.height > innerHeight * .85) score -= 45;
    if (el.querySelector && el.querySelector('canvas, img, svg')) score -= 18;

    return {el, score, area: r.width * r.height};
  }).sort((a, b) => b.score - a.score || a.area - b.area);

  if (!scored.length || scored[0].score < 5) return null;

  const el = scored[0].el;
  if (el.id) return '#' + CSS.escape(el.id);

  const tag = el.tagName.toLowerCase();
  const cls = typeof el.className === 'string'
    ? el.className.trim().split(/\s+/).filter(Boolean)
    : [];

  if (cls.length) {
    const selector = tag + cls.map(c => '.' + CSS.escape(c)).join('');
    try {
      if (document.querySelectorAll(selector).length === 1) return selector;
    } catch (_) {}
  }

  const parts = [];
  let node = el;
  while (node && node.nodeType === 1 && node !== document.documentElement) {
    let part = node.tagName.toLowerCase();
    const parent = node.parentElement;
    if (parent) {
      const siblings = [...parent.children].filter(x => x.tagName === node.tagName);
      if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
    }
    parts.unshift(part);
    node = parent;
  }
  return parts.join(' > ');
}
"""


class QRMonitor:
    # Considera o QR ativado quando ele ja foi capturado e desaparece por
    # algumas verificacoes consecutivas. O estado fica salvo no perfil.
    ACTIVATION_MISSING_LIMIT = 4

    def __init__(
        self,
        url: str,
        selector: str = "auto",
        interval: float = 1.0,
        headless: bool = False,
        profile_dir: str | Path | None = None,
    ):
        self.url = url
        self.selector = (selector or "auto").strip()
        self.interval = max(0.5, float(interval))
        self.headless = bool(headless)
        self.profile_dir = Path(profile_dir) if profile_dir else CAPTURE_DIR / "browser_profiles" / "default"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.image_path = CAPTURE_DIR / "latest.png"
        self.activation_file = self.profile_dir / ".qr_activated"
        self.qr_activated = self.activation_file.exists()
        self.qr_seen = False
        self._missing_count = 0

        self.last_capture = None
        self.last_change = None
        self.last_error = None
        self.detected_selector = None
        self.running = False
        self.capture_count = 0

        self._stop_event = threading.Event()
        self._context = None

    def status(self):
        return {
            "running": self.running,
            "source_url": self.url,
            "selector": self.selector,
            "detected_selector": self.detected_selector,
            "last_capture": self.last_capture,
            "last_change": self.last_change,
            "last_error": self.last_error,
            "capture_count": self.capture_count,
            "image_available": self.image_path.exists(),
            "qr_activated": self.qr_activated,
        }

    def _find_selector(self, page):
        if self.selector.lower() != "auto":
            return self.selector
        return page.evaluate(AUTO_DETECT_JS)

    def _mark_qr_missing(self):
        if not self.qr_seen or self.qr_activated:
            return

        self._missing_count += 1
        if self._missing_count >= self.ACTIVATION_MISSING_LIMIT:
            self.qr_activated = True
            self.last_error = None
            try:
                self.activation_file.write_text(
                    datetime.now(timezone.utc).isoformat(), encoding="utf-8"
                )
            except OSError as exc:
                LOG.warning("Nao foi possivel salvar o estado do QR ativado: %s", exc)

    def _capture(self, page):
        # Depois da ativacao, congela a ultima imagem. Nao tira novas capturas,
        # nao substitui latest.png e nao provoca o efeito de piscar no painel.
        if self.qr_activated:
            return False

        selector = self._find_selector(page)
        if not selector:
            self.last_error = (
                "Aguardando elemento visual/QR Code. A deteccao continuara tentando."
            )
            self._mark_qr_missing()
            return False

        self.detected_selector = selector
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=1800)
        except PlaywrightTimeout:
            self.last_error = f"Elemento '{selector}' ainda nao esta visivel; nova tentativa em seguida."
            self._mark_qr_missing()
            return False

        self.qr_seen = True
        self._missing_count = 0

        try:
            locator.evaluate("""el => {
              if (el.tagName === 'IMG' && !el.complete) {
                return new Promise(resolve => {
                  el.addEventListener('load', resolve, {once:true});
                  el.addEventListener('error', resolve, {once:true});
                  setTimeout(resolve, 2000);
                });
              }
              return true;
            }""")
        except Exception:
            pass

        tmp_path = self.image_path.with_suffix(".tmp.png")
        try:
            locator.screenshot(path=str(tmp_path), timeout=10000)
            new_bytes = tmp_path.read_bytes()
            old_bytes = self.image_path.read_bytes() if self.image_path.exists() else None
            changed = new_bytes != old_bytes
            # Evita regravar a imagem se o conteudo nao mudou.
            if changed:
                os.replace(tmp_path, self.image_path)
            else:
                tmp_path.unlink(missing_ok=True)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        now = datetime.now(timezone.utc).isoformat()
        self.last_capture = now
        self.capture_count += 1
        self.last_error = None
        if changed:
            self.last_change = now
        return changed

    def stop(self):
        self._stop_event.set()

    def run(self):
        self.running = True
        self._stop_event.clear()

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    viewport={"width": 1440, "height": 1000},
                    args=["--disable-background-timer-throttling"],
                )
                self._context = context

                pages = context.pages
                page = next(
                    (candidate for candidate in pages if candidate.url not in ("about:blank", "")),
                    pages[0] if pages else context.new_page(),
                )

                # Nunca recarrega uma aba existente. So navega se o perfil abriu
                # sem nenhuma pagina de origem (aba vazia).
                if page.url in ("about:blank", ""):
                    page.goto(self.url, wait_until="domcontentloaded", timeout=60000)

                while not self._stop_event.is_set():
                    if page.is_closed():
                        break

                    if not self.qr_activated:
                        try:
                            self._capture(page)
                        except PlaywrightTimeout:
                            self.last_error = "A pagina demorou para responder; nova tentativa em seguida."
                            self._mark_qr_missing()
                        except Exception as exc:
                            self.last_error = str(exc)

                    # Mesmo depois da ativacao, mantem o navegador aberto e a
                    # sessao viva; apenas interrompe o monitoramento/captura do QR.
                    self._stop_event.wait(self.interval)

                try:
                    context.close()
                except Exception:
                    pass

        except Exception as exc:
            self.last_error = str(exc)
            LOG.error("Falha ao iniciar/monitorar navegador: %s", exc)

        finally:
            self._context = None
            self.running = False
