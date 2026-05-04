import os
import sys
import argparse
from tqdm import tqdm
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py.core.config import DIRECTION_MAP, load_glossary, setup_logging
from py.core.translators import GeminiTranslator, ClaudeTranslator, FreeTranslator
from py.core.document_processor import PDFProcessor, PPTXProcessor

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="PDF/PPTX AI Translator CLI")
    parser.add_argument("input_path", help="Path to input PDF or PPTX file")
    parser.add_argument("--direction", choices=list(DIRECTION_MAP.keys()), default="한국어 → English", help="Translation direction")
    parser.add_argument("--provider", choices=["Free", "Gemini", "Claude"], default="Free", help="AI Provider")
    parser.add_argument("--prompt", default="Translate maintaining a professional business tone.", help="System Instruction")
    args = parser.parse_args()

    input_path = args.input_path
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    dir_info = DIRECTION_MAP[args.direction]
    glossary = load_glossary()

    if args.provider == "Gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("GEMINI_API_KEY environment variable is missing.")
            return
        translator = GeminiTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, args.prompt)
    elif args.provider == "Claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ANTHROPIC_API_KEY environment variable is missing.")
            return
        translator = ClaudeTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, args.prompt)
    else:
        translator = FreeTranslator(dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, args.prompt)

    ext = os.path.splitext(input_path)[1].lower()
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res_dir = os.path.join(base_dir, "result", timestamp)
    os.makedirs(res_dir, exist_ok=True)
    out_name = os.path.basename(input_path).replace(ext, f"_translated_{args.direction.replace(' → ', '2')}{ext}")
    output_path = os.path.join(res_dir, out_name)

    processor = None
    if ext == ".pdf":
        processor = PDFProcessor(translator)
    elif ext == ".pptx":
        processor = PPTXProcessor(translator)
    else:
        print("Unsupported file format.")
        return

    pbar = None
    def progress_callback(current, total, text=""):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, desc="Processing", colour="green")
        
        if total != pbar.total:
            pbar.total = total
            
        if current > pbar.n:
            pbar.update(current - pbar.n)
            
        if text:
            pbar.set_description(text)

    try:
        success = processor.process(input_path, output_path, progress_callback)
        if pbar: pbar.close()
        
        if success:
            print(f"\n✅ Translation complete: {output_path}")
        else:
            print("\n❌ Translation failed.")
    except Exception as e:
        if pbar: pbar.close()
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
