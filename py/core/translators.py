import os
import json
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

class SpendingCapExceeded(Exception):
    pass

class BaseTranslator(ABC):
    def __init__(self, src_lang_code, tgt_lang_code, src_lang_name, tgt_lang_name, glossary, system_instruction):
        self.src_lang_code = src_lang_code
        self.tgt_lang_code = tgt_lang_code
        self.src_lang_name = src_lang_name
        self.tgt_lang_name = tgt_lang_name
        self.glossary = glossary
        self.system_instruction = system_instruction
        self.batch_size = 10
        self.max_workers = 5
        self.sleep_between_batches = 0.5

    @abstractmethod
    def translate_batch(self, batch_texts):
        pass

    @abstractmethod
    def shrink_text(self, text, limit=1000):
        pass

    def translate_all_concurrent(self, texts, progress_callback=None):
        total = len(texts)
        results = [None] * total
        batches = [(i, texts[i:i+self.batch_size]) for i in range(0, total, self.batch_size)]
        
        spending_cap_hit = False
        completed = 0

        def _worker(batch_info):
            nonlocal spending_cap_hit
            if spending_cap_hit: return None
            start_idx, batch_texts = batch_info
            try:
                res = self.translate_batch(batch_texts)
                if self.sleep_between_batches > 0:
                    time.sleep(self.sleep_between_batches)
                return start_idx, res
            except SpendingCapExceeded:
                spending_cap_hit = True
                raise
            except Exception as e:
                logging.error(f"Worker Error: {e}")
                return start_idx, batch_texts

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_worker, b): b for b in batches}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        start_idx, translated_batch = result
                        for j, t in enumerate(translated_batch):
                            results[start_idx + j] = t
                        completed += len(translated_batch)
                        if progress_callback:
                            progress_callback(completed, total)
                except SpendingCapExceeded:
                    pass

        # Free API Fallback
        missing_indices = [i for i, r in enumerate(results) if r is None]
        if missing_indices:
            logging.info(f"Using FreeTranslator fallback for {len(missing_indices)} items.")
            from py.core.translators import FreeTranslator
            free_t = FreeTranslator(self.src_lang_code, self.tgt_lang_code, self.src_lang_name, self.tgt_lang_name, self.glossary, self.system_instruction)
            for i in missing_indices:
                results[i] = free_t.translate_batch([texts[i]])[0]
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
                    
        return results


class GeminiTranslator(BaseTranslator):
    def __init__(self, api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from google import genai
        self.client = genai.Client(api_key=api_key)

    def translate_batch(self, batch_texts):
        if not batch_texts: return batch_texts
        from google.genai import types
        input_dict = {str(i): text for i, text in enumerate(batch_texts)}
        prompt = f"Translate this JSON object from {self.src_lang_name} into {self.tgt_lang_name}. Output ONLY a valid JSON object.\n\n" + json.dumps(input_dict, ensure_ascii=False)
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt, 
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction, 
                    temperature=0.0, 
                    response_mime_type="application/json"
                )
            )
            rj = json.loads(response.text)
            return [rj.get(str(i), batch_texts[i]) for i in range(len(batch_texts))]
        except Exception as e:
            if "spending cap" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
                raise SpendingCapExceeded(str(e))
            logging.error(f"Gemini API Error: {e}")
            return batch_texts

    def shrink_text(self, text, limit=1000):
        if len(text) <= limit: return text
        from google.genai import types
        prompt = f"Summarize the following text so it fits within {limit} characters, keeping the main points and translating to {self.tgt_lang_name} if needed.\n\nText:\n{text}"
        try:
            resp = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            return resp.text.strip()
        except Exception as e:
            logging.error(f"Gemini Shrink Error: {e}")
            return text[:limit]


class ClaudeTranslator(BaseTranslator):
    def __init__(self, api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def translate_batch(self, batch_texts):
        if not batch_texts: return batch_texts
        input_dict = {str(i): text for i, text in enumerate(batch_texts)}
        prompt = f"Translate this JSON object from {self.src_lang_name} into {self.tgt_lang_name}. Output ONLY a valid JSON object.\n\n" + json.dumps(input_dict, ensure_ascii=False)
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                temperature=0.0,
                system=self.system_instruction,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            rj = json.loads(response_text)
            return [rj.get(str(i), batch_texts[i]) for i in range(len(batch_texts))]
        except Exception as e:
            logging.error(f"Claude API Error: {e}")
            return batch_texts

    def shrink_text(self, text, limit=1000):
        if len(text) <= limit: return text
        prompt = f"Summarize the following text so it fits within {limit} characters, keeping the main points and translating to {self.tgt_lang_name} if needed.\n\nText:\n{text}"
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logging.error(f"Claude Shrink Error: {e}")
            return text[:limit]


class FreeTranslator(BaseTranslator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from deep_translator import GoogleTranslator
        self.client = GoogleTranslator(source=self.src_lang_code, target=self.tgt_lang_code)
        self.batch_size = 1
        self.max_workers = 1

    def translate_batch(self, batch_texts):
        if not batch_texts: return batch_texts
        try:
            return self.client.translate_batch(batch_texts)
        except Exception as e:
            logging.error(f"Free API Error: {e}")
            return batch_texts

    def shrink_text(self, text, limit=1000):
        if len(text) <= limit: return text
        try:
            return self.client.translate(text[:limit])
        except Exception:
            return text[:limit]
