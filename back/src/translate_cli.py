import os
import sys
import argparse
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import DIRECTION_MAP, load_glossary, setup_logging
from core.translators import GeminiTranslator, ClaudeTranslator, FreeTranslator
from core.document_processor import PDFProcessor, PPTXProcessor

def main():
    parser = argparse.ArgumentParser(description="AI Document Translator CLI")
    parser.add_argument("input", help="Path to input file (.pdf or .pptx)")
    parser.add_argument("output", help="Path to output file")
    parser.add_argument("--direction", default="한국어 → English", choices=list(DIRECTION_MAP.keys()), help="Translation direction")
    parser.add_argument("--provider", default="Gemini", choices=["Gemini", "Claude", "Free"], help="Translation provider")
    parser.add_argument("--api_key", help="API Key for Gemini or Claude")
    parser.add_argument("--test", action="store_true", help="Test mode (only first 10 pages/slides)")
    
    args = parser.parse_args()
    
    setup_logging()
    
    dir_info = DIRECTION_MAP[args.direction]
    glossary = load_glossary()
    
    ext = os.path.splitext(args.input)[1].lower()
    
    try:
        if args.provider == "Gemini":
            translator = GeminiTranslator(args.api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, "Professional translation")
        elif args.provider == "Claude":
            translator = ClaudeTranslator(args.api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, "Professional translation")
        else:
            translator = FreeTranslator(dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, "Professional translation")
            
        translator.src_regex = dir_info.get("src_regex", ".*")
        
        processor = PDFProcessor(translator) if ext == ".pdf" else PPTXProcessor(translator)
        
        def cb(c, t, txt="", log_msg=""):
            if log_msg:
                print(f"[{c}/{t}] {log_msg}")
            elif txt:
                print(f"[{c}/{t}] {txt}")
        
        success = processor.process(args.input, args.output, cb, test_mode=args.test)
        if success:
            print(f"Successfully translated: {args.output}")
        else:
            print("Translation failed.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
