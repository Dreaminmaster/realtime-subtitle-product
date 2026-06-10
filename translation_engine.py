"""
Translation Engine - Multi-mode translation backend.

Supports:
  - Mode A (Fast): System-level translation via macOS NLP
  - Mode B (Online): OpenAI-compatible API translation  
  - Mode C (Local): Local LLM via LM Studio / Ollama / OpenAI-compatible
  - Mode D (Off): No translation, original text only
"""

import os
import re
import json
import urllib.request
import urllib.error


class BaseTranslator:
    """Base translator interface"""
    
    def translate(self, text: str) -> str:
        raise NotImplementedError
    
    def check_health(self) -> bool:
        """Check if backend is available"""
        return True
    
    @property
    def name(self) -> str:
        raise NotImplementedError


class OfflineTranslator(BaseTranslator):
    """Mode A: macOS system-level translation (no network, fast)"""
    
    name = "System Translation (macOS)"
    
    def __init__(self, target_lang="zh-Hans"):
        self.target_lang = target_lang
        self._available = None
    
    def check_health(self) -> bool:
        if self._available is not None:
            return self._available
        
        try:
            import objc
            from Foundation import NSLinguisticTagger
            self._available = True
        except ImportError:
            self._available = False
        return self._available
    
    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        
        # macOS system translation is limited - for now use
        # simple approach: try Apple's Translation framework if available
        try:
            import objc
            from Foundation import NSLinguisticTagger, NSString
            
            # NSLinguisticTagger can identify language but full translation
            # requires Translation.framework (macOS 11+)
            # For now, fallback to online or local
            raise NotImplementedError("macOS Translation framework requires native Swift bridge")
        except ImportError:
            pass
        
        return "[System Translation: requires macOS 11+ Translation.framework]"


class OnlineAPITranslator(BaseTranslator):
    """Mode B: Online API translation (OpenAI-compatible)"""
    
    name = "Online API"
    
    def __init__(self, target_lang="Chinese", base_url=None, api_key=None, model="gpt-3.5-turbo"):
        self.target_lang = target_lang
        self.model = model
        self.previous_text = ""
        self.previous_translation = ""
        
        # URLs to try in order
        self.base_url = base_url
        self.api_key = api_key
        
        self._client = None
    
    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI
            import httpx
            
            http_client = httpx.Client(verify=False, timeout=15.0)
            self._client = OpenAI(
                api_key=self.api_key or os.getenv("OPENAI_API_KEY", "dummy-key"),
                base_url=self.base_url or os.getenv("OPENAI_BASE_URL"),
                http_client=http_client
            )
        return self._client
    
    def check_health(self) -> bool:
        try:
            client = self._ensure_client()
            client.models.list(timeout=5.0)
            return True
        except Exception:
            return False
    
    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        
        client = self._ensure_client()
        
        system_prompt = (
            f"You are a professional real-time translator. "
            f"Translate the following input into {self.target_lang}. "
            f"Output ONLY the translation, no explanations."
        )
        
        if self.previous_text:
            system_prompt += (
                f"\n\nPrevious context for continuity:\n"
                f"Previous: \"{self.previous_text}\"\n"
                f"Previous translation: \"{self.previous_translation}\""
            )
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=10.0
            )
            result = response.choices[0].message.content.strip()
            
            # Strip thinking tags
            result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
            
            self.previous_text = text
            self.previous_translation = result
            return result
            
        except Exception as e:
            print(f"[OnlineTranslator] Error: {e}")
            return "[Translation Failed]"


class LocalLLMTranslator(OnlineAPITranslator):
    """Mode C: Local LLM (LM Studio / Ollama / etc)"""
    
    name = "Local LLM"
    
    def __init__(self, target_lang="Chinese", base_url="http://localhost:1234/v1", 
                 api_key="not-needed", model="local-model"):
        super().__init__(target_lang=target_lang, base_url=base_url, 
                        api_key=api_key, model=model)


class CustomAPITranslator(OnlineAPITranslator):
    """Mode D: Custom OpenAI-compatible API"""
    
    name = "Custom API"
    
    def __init__(self, target_lang="Chinese", base_url=None, api_key=None, model=None):
        super().__init__(target_lang=target_lang, base_url=base_url,
                        api_key=api_key, model=model or "gpt-3.5-turbo")


class NoopTranslator(BaseTranslator):
    """Mode Off: No translation"""
    
    name = "No Translation"
    
    def translate(self, text: str) -> str:
        return ""
    
    def check_health(self) -> bool:
        return True


class TranslationEngine:
    """
    Singleton translation engine that manages multiple backends.
    """
    
    MODES = {
        "off": "No Translation",
        "fast": "System Translation",
        "online": "Online API",
        "local": "Local LLM",
        "custom": "Custom API"
    }
    
    def __init__(self):
        self._current_mode = "online"
        self._translator: BaseTranslator = None
        self._translators = {}
        self.target_lang = "Chinese"
    
    def set_mode(self, mode: str, **kwargs):
        """Switch translation mode"""
        if mode not in self.MODES:
            raise ValueError(f"Unknown mode: {mode}. Available: {list(self.MODES.keys())}")
        
        self._current_mode = mode
        
        if mode == "off":
            self._translator = NoopTranslator()
        elif mode == "fast":
            self._translator = OfflineTranslator(target_lang=self.target_lang)
        elif mode == "online":
            self._translator = OnlineAPITranslator(
                target_lang=self.target_lang,
                base_url=kwargs.get("base_url"),
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "gpt-3.5-turbo")
            )
        elif mode == "local":
            self._translator = LocalLLMTranslator(
                target_lang=self.target_lang,
                base_url=kwargs.get("base_url", "http://localhost:1234/v1"),
                model=kwargs.get("model", "local-model")
            )
        elif mode == "custom":
            self._translator = CustomAPITranslator(
                target_lang=self.target_lang,
                base_url=kwargs.get("base_url"),
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model")
            )
        
        self._translators[mode] = self._translator
        
        print(f"[TranslationEngine] Switched to '{mode}' mode ({self._translator.name})")
        return self._translator
    
    def translate(self, text: str) -> str:
        if self._translator is None:
            self.set_mode("online")
        return self._translator.translate(text)
    
    def check_health(self) -> dict:
        """Check health of current backend"""
        if self._translator is None:
            return {"mode": "none", "available": False, "error": "No translator initialized"}
        
        try:
            available = self._translator.check_health()
            return {
                "mode": self._current_mode,
                "name": self._translator.name,
                "available": available
            }
        except Exception as e:
            return {
                "mode": self._current_mode,
                "name": self._translator.name,
                "available": False,
                "error": str(e)
            }
    
    @property
    def current_mode(self) -> str:
        return self._current_mode
    
    @property
    def current_name(self) -> str:
        if self._translator:
            return self._translator.name
        return "Not initialized"


# Global singleton
translation_engine = TranslationEngine()
