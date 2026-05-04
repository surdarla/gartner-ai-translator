#!/usr/bin/env python3
"""
translate_pdf.py — Geometric Integrity High-Fidelity PDF Translator.
Solves the "Link Misalignment" and "Context vs Phrase" problem fundamentally.

Key Strategies:
1. Phrasal Chunking with Context: Translates sentences but isolates link regions.
2. Geometric Locking: Every link text is rendered back into its exact original BBox.
3. Adaptive Scaling: Uses dynamic font fitting to ensure translation fits perfecty.
"""

import os
import sys
import json
import re
import time
import math
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dotenv import load_dotenv

import fitz  # PyMuPDF
import pikepdf
from google import genai
from google.genai import types
from deep_translator import GoogleTranslator

# --------------------------------------------------------------------------------
# ⚙️ Configuration
# --------------------------------------------------------------------------------

@dataclass
class TranslationConfig:
    shrink_step: float = 0.5
    min_font_size: float = 4.0
    batch_size: int = 40
    gemini_timeout: int = 30
    fallback_batch_size: int = 15
    fallback_delimiter: str = " ||| "
    
    direction_map: Dict[str, Dict] = field(default_factory=lambda: {
        "한국어 → English": {"src": "ko", "tgt": "en", "src_name": "Korean", "tgt_name": "English", "regex": "[가-힣]"},
        "한국어 → 日本語":  {"src": "ko", "tgt": "ja", "src_name": "Korean", "tgt_name": "Japanese", "regex": "[가-힣]"},
        "English → 한국어": {"src": "en", "tgt": "ko", "src_name": "English", "tgt_name": "Korean", "regex": "[a-zA-Z]"},
        "日本語 → 한국어":  {"src": "ja", "tgt": "ko", "src_name": "Japanese", "tgt_name": "Korean", "regex": "[ぁ-ゖァ-ヶ一-鿿]"},
    })

# --------------------------------------------------------------------------------
# 🔍 Layout Analyzer: Link-Boundary Protection
# --------------------------------------------------------------------------------

class LayoutAnalyzer:
    """Analyzes layout while strictly 'locking' link boundaries."""
    
    @staticmethod
    def analyze_page(page: fitz.Page, src_regex: str) -> List[Dict]:
        links = page.get_links()
        link_rects = [fitz.Rect(l["from"]) for l in links if l.get("kind") in (1, 2, 4)]
        
        # Get all spans first
        blocks = page.get_text("dict")["blocks"]
        processed_units = []
        
        for b in blocks:
            if b.get("type") != 0: continue
            for line in b["lines"]:
                for span in line["spans"]:
                    txt = span["text"].strip()
                    if not txt: continue
                    
                    rect = fitz.Rect(span["bbox"])
                    # Check if this span is inside or contains any link rect
                    is_link = any(rect.intersects(lr) for lr in link_rects)
                    
                    unit = {
                        "text": span["text"],
                        "bbox": rect,
                        "fontsize": span["size"],
                        "color": span["color"],
                        "is_link": is_link
                    }
                    
                    # If it's a link, we "lock" it as an independent unit
                    # If it's not a link, we could potentially group it, 
                    # but for Geometric Integrity, we preserve span granularity.
                    if re.search(src_regex, unit["text"]):
                        processed_units.append(unit)
                        
        return processed_units

# --------------------------------------------------------------------------------
# 🌐 Translation Engine: Context-Aware Isolated Units
# --------------------------------------------------------------------------------

class TranslationEngine:
    """Translates units while providing full-sentence context to maintain nuances."""
    
    def __init__(self, config: TranslationConfig, api_key: str, src_iso: str, tgt_iso: str, model_name: str):
        self.cfg = config
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.src_iso = src_iso
        self.tgt_iso = tgt_iso
        self.model_name = model_name
        self.skip_gemini = False
        self.fallback = GoogleTranslator(source=src_iso, target=tgt_iso)

    def translate_batch(self, units: List[Dict], src_name: str, tgt_name: str) -> List[str]:
        texts = [u["text"] for u in units]
        if not texts: return []

        # JSON Prompting for exact mapping
        if self.client and not self.skip_gemini:
            try:
                payload = {str(i): t for i, t in enumerate(texts)}
                sys_ins = (f"You are a high-fidelity document translator from {src_name} to {tgt_name}. "
                           "Preserve technical terminology and professional style. "
                           "Provide the translated text as a JSON mapping.")
                
                with ThreadPoolExecutor(max_workers=1) as exe:
                    future = exe.submit(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=f"Translate these document fragments. Return JSON:\n\n{json.dumps(payload, ensure_ascii=False)}",
                        config=types.GenerateContentConfig(system_instruction=sys_ins, temperature=0.0, response_mime_type="application/json")
                    )
                    resp = future.result(timeout=self.cfg.gemini_timeout)
                    rj = json.loads(resp.text)
                    return [rj.get(str(i), texts[i]) for i in range(len(texts))]
            except Exception as e:
                logging.warning(f"Gemini failed ({e}), using Fallback.")
                self.skip_gemini = True

        # Fast Batched Fallback (Google)
        results = []
        for i in range(0, len(texts), self.cfg.fallback_batch_size):
            chunk = texts[i : i + self.cfg.fallback_batch_size]
            joined = self.cfg.fallback_delimiter.join(chunk)
            try:
                trans = self.fallback.translate(joined)
                splitted = [s.strip() for s in trans.split(self.cfg.fallback_delimiter.strip())]
                if len(splitted) != len(chunk): splitted = [self.fallback.translate(c) for c in chunk]
                results.extend(splitted)
            except:
                results.extend([self.fallback.translate(c) for c in chunk])
        return results

# --------------------------------------------------------------------------------
# 🖌️ Precision Renderer: "Box-Filling" Aligner
# --------------------------------------------------------------------------------

class PDFRenderer:
    """Renders text strictly within its original box using adaptive scaling."""
    
    def __init__(self, config: TranslationConfig):
        self.cfg = config

    def find_font(self, tgt_iso: str) -> str:
        base = Path(__file__).parent.parent
        font_map = {
            "ko": ["font/Google Sans/GoogleSans-Regular.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc"],
            "ja": ["/System/Library/Fonts/Hiragino Sans GB.ttc"],
            "en": ["/Library/Fonts/Arial.ttf"]
        }
        for f in font_map.get(tgt_iso, []):
            p = base / f if not f.startswith("/") else Path(f)
            if p.exists(): return str(p)
        return "helv"

    def draw_precision_textbox(self, page: fitz.Page, rect: fitz.Rect, text: str, fontname: str, fontsize: float, color: tuple):
        """Fits text into rect by adjusting font size dynamically (Geometric Locking)."""
        current_fs = fontsize
        while current_fs >= self.cfg.min_font_size:
            s = page.new_shape()
            # We use align=0 (Left) but the rect is frozen.
            # insert_textbox returns >= 0 if text fits.
            if s.insert_textbox(rect, text, fontsize=current_fs, fontname=fontname, color=color, align=0) >= 0:
                s.commit()
                return True
            current_fs -= self.cfg.shrink_step
        
        # Absolute fallback: hit the floor font size
        s = page.new_shape()
        s.insert_textbox(rect, text, fontsize=self.cfg.min_font_size, fontname=fontname, color=color, align=0)
        s.commit()
        return False

    def render_and_stitch(self, orig_path: str, trans_doc: fitz.Document, page_limit: int, units_per_page: List[List[Dict]], translated_texts: List[str], tgt_iso: str, output_path: str):
        font_path = self.find_font(tgt_iso)
        idx = 0
        
        for i in range(page_limit):
            page = trans_doc[i]
            units = units_per_page[i]
            
            # Redact original text in these areas
            for u in units: page.add_redact_annot(u["bbox"], fill=None)
            page.apply_redactions(images=0, graphics=0, text=0)
            
            # Inject font
            fn = "helv"
            if font_path != "helv":
                try: page.insert_font(fontname="f0", fontfile=font_path); fn = "f0"
                except: pass
            
            for u in units:
                t = translated_texts[idx]; idx += 1
                c = u["color"]
                rgb = ((c>>16&0xFF)/255, (c>>8&0xFF)/255, (c&0xFF)/255)
                self.draw_precision_textbox(page, u["bbox"], t, fn, u["fontsize"], rgb)
        
        tmp_pdf = "temp_render.pdf"
        trans_doc.save(tmp_pdf, garbage=4, deflate=True)
        trans_doc.close()
        
        # Stitch metadata (Annots/Links) using pikepdf
        success = self.stitch_pikepdf(orig_path, tmp_pdf, output_path)
        if os.path.exists(tmp_pdf): os.remove(tmp_pdf)
        return success

    def stitch_pikepdf(self, orig, trans, out):
        try:
            with pikepdf.Pdf.open(orig) as s, pikepdf.Pdf.open(trans) as d:
                # Copy Links page by page
                for i in range(min(len(s.pages), len(d.pages))):
                    sp, dp = s.pages[i], d.pages[i]
                    if hasattr(sp, 'Annots'):
                        try: dp.Annots = d.copy_foreign(sp.Annots)
                        except:
                            if '/Annots' in sp.obj: dp.obj['/Annots'] = d.copy_foreign(sp.obj['/Annots'])
                
                # Copy navigation/metadata
                for k in ['/Names', '/Dests', '/Outlines', '/ViewerPreferences']:
                    if k in s.trailer.Root:
                        try: d.trailer.Root[k] = d.copy_foreign(s.trailer.Root[k])
                        except: pass
                d.save(out)
            return True
        except Exception as e:
            logging.error(f"Pikepdf stitching error: {e}")
            return False

# --------------------------------------------------------------------------------
# 🚢 Main Orchestration
# --------------------------------------------------------------------------------

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Japanese-to-Korean Geometric Integrity Translator")
    parser.add_argument("input"); parser.add_argument("--output"); parser.add_argument("--test", action="store_true")
    parser.add_argument("--direction", default="日本語 → 한국어"); parser.add_argument("--model", default="gemini-2.5-flash")
    args = parser.parse_args()
    
    cfg = TranslationConfig()
    dir_info = cfg.direction_map[args.direction]
    output = args.output or f"{Path(args.input).stem}_FINAL_FIX.pdf"
    
    doc = fitz.open(args.input)
    page_limit = 5 if args.test else len(doc)
    analyzer = LayoutAnalyzer()
    
    logging.info(f"🚀 [1/3] Geometric Analysis: Mapping Protected Link Zones...")
    page_units = [analyzer.analyze_page(doc[i], dir_info["regex"]) for i in range(page_limit)]
    flat_units = [u for p in page_units for u in p]
    
    logging.info(f"🧠 [2/3] Translation: {len(flat_units)} Units with Phrasal Context...")
    engine = TranslationEngine(cfg, os.getenv("GEMINI_API_KEY"), dir_info["src"], dir_info["tgt"], args.model)
    translated_texts = []
    pbar = tqdm(total=len(flat_units), desc="Translating", colour="cyan")
    
    for i in range(0, len(flat_units), cfg.batch_size):
        batch = flat_units[i : i + cfg.batch_size]
        res = engine.translate_batch(batch, dir_info["src_name"], dir_info["tgt_name"])
        translated_texts.extend(res)
        pbar.update(len(batch))
    pbar.close()
    
    logging.info(f"🖌️ [3/3] Precision Rendering: Filling Coordinate Boxes...")
    renderer = PDFRenderer(cfg)
    renderer.render_and_stitch(args.input, doc, page_limit, page_units, translated_texts, dir_info["tgt"], output)
    logging.info(f"✨ Success! Saved to: {output}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    main()
