"""
Inquisidor Jurídico v7.0 — V.victor Digital Flow
Sistema Multi-Agente com redundância dupla (NVIDIA + Gemini),
memória persistente criptografada, cache SHA256, chunking,
verificação de citações e proteção contra injeção de prompt.
"""
import os
import sys
import re
import json
import time
import hashlib
import logging
import logging.handlers
import datetime
import sqlite3
import traceback
import threading
import concurrent.futures
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont

os.environ['TERM'] = 'dumb'
os.environ['NO_COLOR'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# ============================================================
# PATHS (persistent even in PyInstaller EXE)
# ============================================================
if getattr(sys, 'frozen', False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(_BASE, 'config.json')
_KEY_PATH = os.path.join(_BASE, 'inquisidor.key')
_LOG_PATH = os.path.join(_BASE, 'inquisidor.log')

# ============================================================
# LOGGING
# ============================================================
_log_config = {
    'level': logging.INFO,
    'max_bytes': 1 * 1024 * 1024,
    'backup_count': 5,
}


def _setup_logging():
    handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=_log_config['max_bytes'],
        backupCount=_log_config['backup_count'], encoding='utf-8')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    root = logging.getLogger()
    root.setLevel(_log_config['level'])
    root.addHandler(handler)
    logging.info('=== Inquisidor Jurídico v7.0 iniciado ===')


_setup_logging()

# ============================================================
# ENCRYPTION
# ============================================================
try:
    from cryptography.fernet import Fernet
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
    logging.warning('cryptography não disponível — chaves em plaintext')


def _gerar_key():
    if not _HAS_CRYPTO:
        return None
    key = Fernet.generate_key()
    with open(_KEY_PATH, 'wb') as f:
        f.write(key)
    os.chmod(_KEY_PATH, 0o600)
    logging.info('Chave de criptografia gerada em %s', _KEY_PATH)
    return key


def _carregar_key():
    if not _HAS_CRYPTO:
        return None
    if os.path.exists(_KEY_PATH):
        with open(_KEY_PATH, 'rb') as f:
            return f.read()
    return _gerar_key()


def _encrypt(texto, key):
    if not _HAS_CRYPTO or not key:
        return texto
    return Fernet(key).encrypt(texto.encode()).decode()


def _decrypt(texto, key):
    if not _HAS_CRYPTO or not key:
        return texto
    try:
        return Fernet(key).decrypt(texto.encode()).decode()
    except Exception:
        logging.error('Falha ao decriptar — chave inválida?')
        return texto


# ============================================================
# CONFIG
# ============================================================
_CONFIG_DEFAULT = {
    'logging': {'level': 'INFO', 'max_mb': 1, 'backup_count': 5},
    'rate_limit': {'min_interval': 2.0, 'max_rpm': 10},
    'chunking': {'max_size': 8000, 'overlap': 300},
    'prompt': {'max_chars': 12000},
    'api': {'temperature': 0.1, 'timeout': 120, 'ping_timeout': 30},
    'retry': {'max_attempts': 3, 'base_delay': 1.0, 'max_delay': 8.0},
    'parallel': {'max_workers': 4},
    'memory': {'max_memory': 50, 'max_feedback': 100, 'ttl_days': 90},
    'obsidian': {'vault_path': ''},
    'encrypted_keys': {},
    'key_file': 'inquisidor.key',
}


def _carregar_config():
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            for k, v in _CONFIG_DEFAULT.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception as e:
            logging.error('Erro ao ler config.json: %s', e)
    return dict(_CONFIG_DEFAULT)


def _salvar_config(cfg):
    try:
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error('Erro ao salvar config.json: %s', e)


_CONFIG = _carregar_config()
_ENCRYPTION_KEY = _carregar_key()


def _obter_api_key(nome_var, nome_config):
    encrypted = _CONFIG.get('encrypted_keys', {}).get(nome_config)
    if encrypted:
        return _decrypt(encrypted, _ENCRYPTION_KEY)
    plain = os.getenv(nome_var, '')
    if plain and _HAS_CRYPTO and _ENCRYPTION_KEY:
        _CONFIG.setdefault('encrypted_keys', {})[nome_config] = _encrypt(plain, _ENCRYPTION_KEY)
        _salvar_config(_CONFIG)
        logging.info('Chave %s criptografada e salva em config.json', nome_config)
    return plain


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# INPUT SANITIZATION
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
_INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?(previous|above|prior)',
    r'ignore\s+(instructions|commands|prompts)',
    r'esqueça\s+(todas\s+)?(as\s+)?(instruções|instrucoes|comandos)',
    r'desconsidere\s+(as\s+)?(instruções|instrucoes|instruções anteriores)',
    r'você\s+é\s+(um\s+)?(assistente|AI|chatbot)',
    r'você\s+deve\s+(ignorar|esquecer|desconsiderar)',
    r'agora\s+você\s+é',
    r'you\s+are\s+(an?\s+)?(assistant|AI|chatbot|now)',
    r'ignore\s+all\s+previous\s+instructions',
    r'ignore\s+(tod[ao]s\s+(as|os)\s+)?(instruções|instrucoes|comandos|ordens)',
]


def sanitizar_prompt(texto):
    texto_sanitizado = texto
    for pattern in _INJECTION_PATTERNS:
        texto_sanitizado = re.sub(pattern, '[BLOQUEADO]', texto_sanitizado, flags=re.IGNORECASE)
    return (
        "=== INÍCIO DA PETIÇÃO ===\n"
        f"{texto_sanitizado}\n"
        "=== FIM DA PETIÇÃO ===\n"
        "Analise APENAS o conteúdo entre os marcadores acima."
    )


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# RATE LIMITER
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
class RateLimiter:
    def __init__(self, min_interval=2.0, max_rpm=10):
        self.min_interval = min_interval
        self.max_rpm = max_rpm
        self._ultima_chamada = 0.0
        self._timestamps = []
        self._lock = threading.Lock()

    def permitir(self):
        with self._lock:
            agora = time.time()
            self._timestamps = [t for t in self._timestamps if t > agora - 60]
            if len(self._timestamps) >= self.max_rpm:
                return False
            delta = agora - self._ultima_chamada
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._ultima_chamada = time.time()
            self._timestamps.append(self._ultima_chamada)
            return True


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# MEMORY AUDITOR
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
class MemoryAuditor:
    """Sistema de Memória Persistente com SQLite, cache e poda automática."""
    DB_PATH = os.path.join(_BASE, "config", "memory.db")

    def __init__(self):
        self.MAX_MEMORY = _CONFIG['memory']['max_memory']
        self.MAX_FEEDBACK = _CONFIG['memory']['max_feedback']
        self.MEMORY_TTL_DAYS = _CONFIG['memory']['ttl_days']
        self._inicializar()
        self._podar()

    def _inicializar(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE, valor TEXT, contexto TEXT, timestamp TEXT
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarefa TEXT, nota INTEGER, comentario TEXT, timestamp TEXT
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_memory_ts ON memory(timestamp)''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_feedback_ts ON feedback(timestamp)''')

    def _podar(self):
        try:
            with sqlite3.connect(self.DB_PATH) as conn:
                cutoff = (datetime.datetime.now() - datetime.timedelta(days=self.MEMORY_TTL_DAYS)).isoformat()
                conn.execute('DELETE FROM memory WHERE timestamp < ?', (cutoff,))
                conn.execute('DELETE FROM memory WHERE id NOT IN (SELECT id FROM memory ORDER BY timestamp DESC LIMIT ?)',
                             (self.MAX_MEMORY,))
                conn.execute('DELETE FROM feedback WHERE id NOT IN (SELECT id FROM feedback ORDER BY timestamp DESC LIMIT ?)',
                             (self.MAX_FEEDBACK,))
            with sqlite3.connect(self.DB_PATH) as conn:
                conn.isolation_level = None
                conn.execute('VACUUM')
        except Exception as e:
            logging.error('Erro na poda: %s', e)

    def salvar(self, chave, valor, contexto=""):
        try:
            with sqlite3.connect(self.DB_PATH) as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO memory (chave, valor, contexto, timestamp) VALUES (?, ?, ?, ?)',
                    (chave, valor, contexto, datetime.datetime.now().isoformat()))
            return True
        except Exception as e:
            logging.error('Erro ao salvar memória: %s', e)
            return False

    def carregar(self, chave):
        try:
            with sqlite3.connect(self.DB_PATH) as conn:
                row = conn.execute('SELECT valor FROM memory WHERE chave = ?', (chave,)).fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def salvar_cache(self, hash_chave, resultado):
        return self.salvar(f"cache_{hash_chave}", resultado, contexto="cache")

    def carregar_cache(self, hash_chave):
        return self.carregar(f"cache_{hash_chave}")

    def registrar_feedback(self, tarefa, nota, comentario=""):
        try:
            with sqlite3.connect(self.DB_PATH) as conn:
                conn.execute(
                    'INSERT INTO feedback (tarefa, nota, comentario, timestamp) VALUES (?, ?, ?, ?)',
                    (tarefa, nota, comentario, datetime.datetime.now().isoformat()))
            return True
        except Exception:
            return False

    def resumo_memoria(self):
        try:
            with sqlite3.connect(self.DB_PATH) as conn:
                rows = conn.execute(
                    'SELECT chave, valor, timestamp FROM memory ORDER BY timestamp DESC LIMIT 5'
                ).fetchall()
                if not rows:
                    return ""
                partes = ["### Memória de Análises Anteriores"]
                for chave, valor, ts in rows:
                    if chave.startswith("analise_"):
                        preview = valor[:200] if valor else ""
                        partes.append(f"- {chave} ({ts[:10]}): {preview}...")
                return "\n".join(partes)
        except Exception:
            return ""


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# LLM MANAGER
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
class LLMManager:
    def __init__(self):
        nvidia_key = _obter_api_key("NVIDIA_API_KEY", "nvidia")
        gemini_key = _obter_api_key("GOOGLE_API_KEY", "gemini")

        self.motores = []
        if nvidia_key:
            self.motores.append({
                "nome": "NVIDIA Llama 3.3 70B",
                "model": "meta/llama-3.3-70b-instruct",
                "api_key": nvidia_key,
                "api_base": "https://integrate.api.nvidia.com/v1",
            })
        if gemini_key:
            self.motores.append({
                "nome": "Gemini 2.0 Flash",
                "model": "gemini-2.0-flash",
                "api_key": gemini_key,
                "api_base": None,
            })
        self.indice_atual = 0
        self.motor_config = None
        self.nomeMotor = None
        self.memoria = MemoryAuditor()
        cfg_rate = _CONFIG['rate_limit']
        self.rate_limiter = RateLimiter(
            min_interval=cfg_rate['min_interval'],
            max_rpm=cfg_rate['max_rpm'])
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4, pool_maxsize=8,
            max_retries=0
        )
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)

    def _api_call(self, prompt, max_tokens=4096, timeout=120):
        motor = self.motor_config
        if not motor:
            raise RuntimeError("Nenhum motor configurado. Execute obter() primeiro.")
        self.rate_limiter.permitir()

        cfg_retry = _CONFIG.get('retry', {'max_attempts': 3, 'base_delay': 1.0, 'max_delay': 8.0})

        ultimo_erro = None
        for tentativa in range(cfg_retry['max_attempts']):
            try:
                if motor.get("api_base"):
                    resp = self._session.post(
                        f"{motor['api_base'].rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {motor['api_key']}", "Content-Type": "application/json"},
                        json={
                            "model": motor["model"],
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": _CONFIG['api']['temperature'],
                            "max_tokens": max_tokens,
                        },
                        timeout=timeout,
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]
                else:
                    resp = self._session.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{motor['model']}:generateContent?key={motor['api_key']}",
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": _CONFIG['api']['temperature'],
                                "maxOutputTokens": max_tokens},
                        },
                        timeout=timeout,
                    )
                    if not resp.ok:
                        resp.raise_for_status()
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

            except requests.exceptions.Timeout as e:
                ultimo_erro = e
                logging.warning('Timeout tentativa %d/%d: %s', tentativa + 1, cfg_retry['max_attempts'], str(e)[:60])
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                if status in (429, 502, 503, 504):
                    ultimo_erro = e
                    logging.warning('HTTP %d tentativa %d/%d', status, tentativa + 1, cfg_retry['max_attempts'])
                else:
                    msg = f"HTTP {status}: {e.response.text[:200]}"
                    logging.error(msg)
                    raise RuntimeError(msg)
            except (KeyError, IndexError, ValueError) as e:
                msg = f"Resposta inesperada da API: {e}"
                logging.error(msg)
                raise RuntimeError(msg)

            if tentativa < cfg_retry['max_attempts'] - 1:
                delay = min(cfg_retry['base_delay'] * (2 ** tentativa), cfg_retry['max_delay'])
                time.sleep(delay)

        raise RuntimeError(f"API falhou após {cfg_retry['max_attempts']} tentativas: {ultimo_erro}")

    def obter(self, status_callback=None):
        while self.indice_atual < len(self.motores):
            motor = self.motores[self.indice_atual]
            if status_callback:
                status_callback(f"Conectando {motor['nome']}...")
            try:
                self.motor_config = motor
                self._api_call("ping", max_tokens=5,
                               timeout=_CONFIG['api']['ping_timeout'])
                self.nomeMotor = motor['nome']
                self.memoria.salvar("motor_ativo", motor['nome'])
                logging.info('Motor ativo: %s', motor['nome'])
                return motor, motor['nome']
            except Exception as e:
                logging.warning('Falha no motor %s: %s', motor['nome'], str(e)[:80])
                self.indice_atual += 1
                self.motor_config = None
        return None, None


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# JURISPRUDENCE SEARCHER  (anti-hallucination via RAG)
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
_TERMOS_LEGAIS = [
    r'(direito\s+(civil|penal|processual|constitucional|tribut[áa]rio|trabalhista|previdenci[áa]rio|empresarial|administrativo|do\s+consumidor|internacional))',
    r'(c[óo]digo\s+(civil|penal|processual\s+civil|processual\s+penal|defesa\s+do\s+consumidor|tribut[áa]rio|eleitoral|trabalhista|comercial|[aá]guas|florestal))',
    r'(lei\s+(n[°º]?\s*)?\d[\d.]*)',
    r'(s[úu]mula\s+(vinculante\s+)?\d+)',
    r'(dano\s+(moral|material|est[é]tico|existencial))',
    r'(responsabilidade\s+(civil|objetiva|subjetiva|solid[áa]ria|contratual|extracontratual))',
    r'(abuso\s+de\s+direito)',
    r'(boa[- ]f[ée])',
    r'(fun[çc][ãa]o\s+social\s+(do\s+)?contrato)',
    r'(enriquecimento\s+(sem\s+causa|il[íi]cito))',
    r'(prescri[çc][ãa]o|decad[êe]ncia)',
    r'(coisa\s+julgada|lite[^s]pend[êe]ncia|conex[ãa]o|contin[êe]ncia)',
    r'(devido\s+processo\s+legal|contradit[óo]rio|ampla\s+defesa)',
]

_AREAS_JURIDICAS = [
    "direito civil", "direito penal", "direito processual civil",
    "direito constitucional", "direito tributário", "direito trabalhista",
    "direito previdenciário", "direito empresarial", "direito do consumidor",
    "direito administrativo", "direito internacional",
    "responsabilidade civil", "direito de família", "direito das obrigações",
    "direito das coisas", "direito contratual",
]


def _extrair_termos_busca(texto):
    termos = set()
    for pattern in _TERMOS_LEGAIS:
        matches = re.findall(pattern, texto, re.IGNORECASE)
        for m in matches:
            if isinstance(m, tuple):
                termos.add(m[0].strip())
            else:
                termos.add(m.strip())
    for area in _AREAS_JURIDICAS:
        if area.lower() in texto.lower():
            termos.add(area)
    leis = _extrair_citacoes(texto)
    for tipo, valor in leis:
        if tipo == 'artigo':
            termos.add(f"artigo {valor}")
        elif tipo == 'lei':
            termos.add(f"lei {valor}")
    return list(termos)[:8]


class JurisprudenceSearcher:
    URL_STJ = "https://scon.stj.jus.br/SCON/pesquisar.jsp"
    URL_STF = "https://jurisprudencia.stf.jus.br/pages/search"

    def __init__(self):
        self._cache = {}
        try:
            from ddgs import DDGS
            self._ddgs = DDGS()
            self._disponivel = True
        except Exception:
            try:
                from duckduckgo_search import DDGS
                self._ddgs = DDGS()
                self._disponivel = True
            except Exception:
                self._disponivel = False

    def buscar_precedentes(self, termo, max_resultados=4):
        if not self._disponivel:
            return []
        termo_key = termo.lower().strip()
        if termo_key in self._cache:
            return self._cache[termo_key]

        resultados = []
        consultas = [
            f"STJ jurisprudência {termo}",
            f"STF {termo}",
            f"{termo} direito doutrina",
        ]
        vistos = set()
        for consulta in consultas:
            try:
                results = list(self._ddgs.text(
                    consulta, max_results=max_resultados
                ))
                for r in results:
                    titulo = r.get("title", "")
                    href = r.get("href", "")
                    body = r.get("body", "")
                    if href in vistos:
                        continue
                    vistos.add(href)
                    resultados.append({
                        "titulo": titulo,
                        "url": href,
                        "resumo": body[:300],
                        "termo": termo,
                    })
                    if len(resultados) >= max_resultados * 2:
                        break
            except Exception:
                continue
        self._cache[termo_key] = resultados
        return resultados

    def buscar_para_peticao(self, texto_peticao, max_por_termo=3):
        termos = _extrair_termos_busca(texto_peticao)
        if not termos:
            return []
        todos = []
        vistos = set()
        for termo in termos[:5]:
            resultados = self.buscar_precedentes(termo, max_por_termo)
            for r in resultados:
                if r["url"] not in vistos:
                    vistos.add(r["url"])
                    todos.append(r)
        return todos[:15]

    def formatar_contexto(self, precedentes):
        if not precedentes:
            return ""
        linhas = ["### PRECEDENTES REAIS ENCONTRADOS (use APENAS estes nas citações)"]
        for i, p in enumerate(precedentes, 1):
            titulo = p["titulo"][:120]
            resumo = p["resumo"][:200]
            url = p["url"]
            linhas.append(f"{i}. {titulo}")
            if resumo:
                linhas.append(f"   {resumo}")
            linhas.append(f"   Fonte: {url}")
            linhas.append("")
        return "\n".join(linhas)

    def verificar_citacao_web(self, tipo, valor):
        if not self._disponivel:
            return "NÃO VERIFICADO"
        cache_key = f"{tipo}:{valor}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        consultas = {
            "artigo": f"\"artigo {valor}\" código civil OR código penal OR CPC site:jusbrasil.com.br OR site:planalto.gov.br",
            "sumula_stj": f"Súmula STJ {valor} site:stj.jus.br OR site:jusbrasil.com.br",
            "sumula_stf": f"Súmula STF {valor} site:stf.jus.br",
            "lei": f"Lei {valor} site:planalto.gov.br",
        }
        consulta = consultas.get(tipo, f"{tipo} {valor} jurídico")
        try:
            results = list(self._ddgs.text(consulta, max_results=3))
            for r in results:
                body = (r.get("title", "") + " " + r.get("body", "")).lower()
                if valor in body:
                    self._cache[cache_key] = "OK"
                    return "OK"
            self._cache[cache_key] = "NÃO VERIFICADO"
            return "NÃO VERIFICADO"
        except Exception:
            return "NÃO VERIFICADO"


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# LEGAL VERIFIER
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
_ARTIGOS = {
    '5', '6', '7', '37', '102', '103', '105', '226', '227',
    '104', '166', '171', '186', '187', '188', '189', '190', '191', '192', '193',
    '421', '422', '423', '424', '425', '426', '427', '428', '429', '430',
    '927', '944',
}
_ARTIGOS.update(str(i) for i in range(300, 381))
_ARTIGOS.update(str(i) for i in range(489, 1081))

_CITACOES_CONHECIDAS = {
    'artigo': _ARTIGOS,
    'sumula_stj': {str(i) for i in range(1, 680)},
    'sumula_stf': {str(i) for i in range(1, 1001)},
    'lei': {
        '10406', '13105', '8078', '9099', '9869', '10259', '11000',
        '11101', '11340', '11419', '12016', '12153', '12376', '12378',
        '12405', '12527', '12711', '12830', '12965', '13019', '13021',
        '13022', '13140', '13146', '13256', '13303', '13363',
    },
}


def _chunk_text(texto, max_size=8000, overlap=300):
    if len(texto) <= max_size:
        return [texto]
    chunks = []
    start = 0
    while start < len(texto):
        end = start + max_size
        if end >= len(texto):
            chunks.append(texto[start:])
            break
        boundary = texto.rfind('\n\n', start, end)
        if boundary < start:
            boundary = texto.rfind('. ', start, end)
            if boundary < start:
                boundary = end
            else:
                boundary += 2
        else:
            boundary += 2
        chunks.append(texto[start:boundary])
        start = boundary - overlap
    return chunks


def _extrair_citacoes(texto):
    citacoes = []
    arts = re.findall(
        r'(?:Art\.|art\.|artigo)\s+(\d+)',
        texto)
    for a in arts:
        citacoes.append(('artigo', a.strip()))
    sumulas_stj = re.findall(
        r'S[úu]mula\s+(?:do\s+)?STJ\s+(?:n[°º]\s*)?(\d+)', texto)
    for s in sumulas_stj:
        citacoes.append(('sumula_stj', s.strip()))
    sumulas_stf = re.findall(
        r'S[úu]mula\s+(?:vinculante\s+)?(?:do\s+)?STF\s+(?:n[°º]\s*)?(\d+)', texto)
    for s in sumulas_stf:
        citacoes.append(('sumula_stf', s.strip()))
    sumulas = re.findall(r'S[úu]mula\s+(?:vinculante\s+)?(\d+)', texto)
    for s in sumulas:
        n = s.strip()
        if n not in [x[1] for x in citacoes]:
            citacoes.append(('sumula', n))
    leis = re.findall(r'Lei\s+(?:n[°º]?\s*)?(\d[\d.]*)', texto)
    for l in leis:
        citacoes.append(('lei', re.sub(r'[.\s]', '', l)))
    return citacoes


def _verificar_citacoes(citacoes, searcher=None):
    resultados = []
    for tipo, valor in citacoes:
        status = 'OK' if (tipo in _CITACOES_CONHECIDAS and valor in _CITACOES_CONHECIDAS[tipo]) else 'NÃO VERIFICADO'
        if status == 'NÃO VERIFICADO' and searcher and tipo in ('artigo', 'sumula_stj', 'sumula_stf', 'lei'):
            status = searcher.verificar_citacao_web(tipo, valor)
        resultados.append((tipo, valor, status))
    return resultados


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# UI — INQUISIDOR V6
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
class InquisidorV6:
    PROMTPS = {
        "analista": (
            "Você é um promotor de justiça com 30 anos de experiência.\n\n"
            "Analise a petição abaixo:\n\n"
            "{texto}\n\n"
            "{precedentes}\n\n"
            "Para cada argumento do adversário:\n"
            "1. IDENTIFIQUE a tese central\n"
            "2. AVALIE a solidez jurídica\n"
            "3. APONTE vulnerabilidades\n"
            "4. CITE artigos (CPC, CC, CF) e precedentes STJ/STF aplicáveis\n\n"
            "REGRAS ABSOLUTAS — VIOLAÇÃO = RELATÓRIO REJEITADO:\n"
            "- Você SÓ pode citar artigos, leis e súmulas que estão na seção PRECEDENTES REAIS acima.\n"
            "- NUNCA invente artigos, súmulas ou jurisprudência.\n"
            "- Se a seção de PRECEDENTES estiver vazia, escreva 'NENHUM PRECEDENTE ENCONTRADO'.\n"
            "- NUNCA cite números de artigos ou súmulas que você 'acha' que existem.\n"
            "- Se um precedente for relevante, COPIE EXATAMENTE o texto da seção de PRECEDENTES.\n\n"
            "Formato obrigatório:\n"
            "- Resumo Executivo (3 linhas)\n"
            "- Quadro de Vulnerabilidades\n"
            "- Teses de Defesa com artigos (APENAS dos precedentes fornecidos)\n"
            "- Precedentes Recomendados"
        ),
        "revisor": (
            "Revise o relatório abaixo como desembargador:\n\n{relatorio}\n\n"
            "1. Elimine contradições\n"
            "2. Verifique se os artigos citados estão na seção de PRECEDENTES fornecida\n"
            "3. REMOVA IMEDIATAMENTE qualquer artigo, lei ou súmula que pareça inventada\n"
            "4. Garanta tom profissional e coesão\n"
            "5. Versão final em formato de relatório jurídico"
        ),
        "verificador": (
            "Você é um corregedor do Conselho Nacional de Justiça.\n"
            "Sua função é ELIMINAR qualquer informação falsa ou inventada deste relatório.\n\n"
            "Relatório a verificar:\n\n{relatorio}\n\n"
            "REGRAS RÍGIDAS:\n"
            "1. Para cada artigo de lei citado (CPC, CC, CF, CDC, etc.):\n"
            "   - Se estiver na seção PRECEDENTES REAIS, mantenha.\n"
            "   - Se tiver DÚVIDA, marque como [NÃO VERIFICADO].\n"
            "   - Se não estiver nos precedentes fornecidos, REMOVA e escreva \"[REMOVIDO — INVENTADO]\".\n\n"
            "2. Para cada súmula ou precedente (STJ, STF):\n"
            "   - Mesma regra: mantenha se nos precedentes, remova se suspeito.\n\n"
            "3. NÃO adicione NENHUMA informação nova.\n"
            "4. NÃO invente justificativas para manter citações.\n"
            "5. Ao final, adicione uma seção \"VERIFICAÇÃO\" listando:\n"
            "   - Total de itens mantidos\n"
            "   - Total removido por suspeita de falsidade\n"
            "   - Total marcado como [NÃO VERIFICADO]\n\n"
            "Saída: o relatório VERIFICADO. Se remover algo suspeito, explique em 1 linha."
        ),
    }

    FONT = ("Segoe UI", 10)
    FONT_BOLD = ("Segoe UI", 10, "bold")
    FONT_MONO = ("Consolas", 10)
    FONT_TITLE = ("Segoe UI", 24, "bold")
    FONT_SUB = ("Segoe UI", 8)
    FONT_SMALL = ("Segoe UI", 7)

    BG = "#0D0D0F"
    CARD = "#16161A"
    CARD_HOVER = "#1E1E24"
    RED = "#E53935"
    RED_HOVER = "#C62828"
    TEXT = "#E8E8E8"
    TEXT_DIM = "#9A9A9A"
    MUTED = "#6B6B6B"
    SUCCESS = "#00C853"
    WARNING = "#FF6D00"
    BORDER = "#2A2A2E"
    GLOW = "#E53935"

    def __init__(self, root):
        self.root = root
        self.root.title("Inquisidor Jurídico v7.0 — V.victor Digital Flow")
        self.root.minsize(960, 640)
        self.root.configure(bg=self.BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Inquisidor.Horizontal.TProgressbar",
            background=self.RED,
            troughcolor=self.CARD,
            bordercolor=self.BORDER,
            lightcolor=self.RED,
            darkcolor=self.RED_HOVER,
            thickness=4
        )
        style.configure(
            "Inquisidor.Vertical.TScrollbar",
            background=self.CARD,
            troughcolor=self.BG,
            bordercolor=self.BORDER,
            arrowcolor=self.TEXT
        )

        self.llm_manager = LLMManager()
        self.memoria = MemoryAuditor()

        self._build_ui()
        self._startup_ping()
        self._pulsar_led()

    def _card(self, parent, **kw):
        f = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, **kw)
        return f

    def _build_ui(self):
        paned = tk.PanedWindow(self.root, bg=self.BG, sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        self.frame_left = tk.Frame(paned, bg=self.BG, width=320)
        paned.add(self.frame_left, minsize=200)

        self._carregar_logo()

        tk.Label(self.frame_left, text="JUSTIÇA É CEGA",
                 fg=self.TEXT, bg=self.BG, font=self.FONT_BOLD).pack(pady=(15, 0))
        tk.Label(self.frame_left, text="O INQUISIDOR NÃO",
                 fg=self.RED, bg=self.BG, font=("Segoe UI", 13, "bold")).pack(pady=(2, 0))

        sep = tk.Frame(self.frame_left, bg=self.BORDER, height=1)
        sep.pack(fill="x", padx=40, pady=(20, 0))

        tk.Label(self.frame_left, text="V.VICTOR DIGITAL FLOW",
                 fg=self.MUTED, bg=self.BG, font=("Segoe UI", 8, "normal")).pack(pady=(10, 0))

        frame_right = tk.Frame(paned, bg=self.BG)
        paned.add(frame_right, minsize=400)

        header = tk.Frame(frame_right, bg=self.BG)
        header.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(header, text="V.VICTOR DIGITAL FLOW",
                 fg=self.RED, bg=self.BG, font=self.FONT_TITLE).pack(anchor="w")
        tk.Label(header, text="SISTEMA DE ESTRATÉGIA DE CONTRADITÓRIO",
                 fg=self.MUTED, bg=self.BG, font=self.FONT_SUB).pack(anchor="w")

        card_input = self._card(frame_right)
        card_input.pack(fill="both", expand=True, padx=24, pady=(15, 0))

        tk.Label(card_input, text="PETIÇÃO ADVERSÁRIA",
                 fg=self.MUTED, bg=self.CARD, font=self.FONT_SUB).pack(anchor="w", padx=12, pady=(10, 0))

        self.txt_input = scrolledtext.ScrolledText(
            card_input, font=self.FONT_MONO,
            bg="#121214", fg=self.TEXT, insertbackground=self.TEXT,
            relief="flat", padx=12, pady=8,
            highlightthickness=0, borderwidth=0
        )
        self.txt_input.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        info_bar = tk.Frame(card_input, bg=self.CARD)
        info_bar.pack(fill="x", padx=12, pady=(0, 12))

        self._placeholder = "Cole a petição adversária para análise..."
        self._has_placeholder = True
        self.txt_input.insert("1.0", self._placeholder)
        self.txt_input.config(fg=self.MUTED)
        self.txt_input.bind("<FocusIn>", self._on_focus_in)
        self.txt_input.bind("<FocusOut>", self._on_focus_out)
        self.txt_input.bind("<KeyRelease>", self._atualizar_contador)

        self.char_counter = tk.Label(
            info_bar, text="0 caracteres",
            fg=self.MUTED, bg=self.CARD, font=self.FONT_SMALL
        )
        self.char_counter.pack(side="left", padx=4)

        self.root.bind("<Control-Return>", lambda e: self.processar())

        control_frame = tk.Frame(frame_right, bg=self.BG)
        control_frame.pack(fill="x", padx=24, pady=(12, 0))

        self.motor_led = tk.Canvas(control_frame, width=10, height=10, bg=self.BG, highlightthickness=0)
        self.motor_led.pack(side="left", padx=(0, 6))
        self._led = self.motor_led.create_oval(0, 0, 10, 10, fill=self.MUTED, outline="")

        self.progresso = ttk.Progressbar(control_frame, mode="indeterminate", length=200,
                                         style="Inquisidor.Horizontal.TProgressbar")
        self.progresso.pack(side="right")
        self.progresso.pack_forget()

        btn_row = tk.Frame(frame_right, bg=self.BG)
        btn_row.pack(fill="x", padx=24, pady=(12, 0))

        self.btn_limpar = tk.Button(
            btn_row, text="LIMPAR",
            command=self._limpar_input,
            bg=self.CARD, fg=self.TEXT_DIM,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            activebackground=self.BORDER, activeforeground=self.TEXT,
            padx=14, pady=10, borderwidth=0
        )
        self.btn_limpar.pack(side="left", padx=(0, 8))
        self.btn_limpar.bind("<Enter>", lambda e: self.btn_limpar.config(bg=self.BORDER))
        self.btn_limpar.bind("<Leave>", lambda e: self.btn_limpar.config(bg=self.CARD))

        self.btn_analisar = tk.Button(
            btn_row, text="INICIAR ATAQUE COORDENADO",
            command=self.processar,
            bg=self.RED, fg="#FFFFFF",
            font=("Segoe UI", 13, "bold"), relief="flat", cursor="hand2",
            activebackground=self.RED_HOVER, activeforeground="#FFFFFF",
            padx=20, pady=10, borderwidth=0
        )
        self.btn_analisar.pack(side="right", fill="x", expand=True)
        self.btn_analisar.bind("<Enter>", lambda e: self.btn_analisar.config(bg=self.RED_HOVER))
        self.btn_analisar.bind("<Leave>", lambda e: self.btn_analisar.config(bg=self.RED))

        status_bar = tk.Frame(frame_right, bg=self.CARD, height=32)
        status_bar.pack(fill="x", padx=24, pady=(12, 16))
        status_bar.pack_propagate(False)

        self.status = tk.Label(
            status_bar, text="Aguardando petição adversária...",
            fg=self.MUTED, bg=self.CARD, font=("Segoe UI", 9), anchor="w"
        )
        self.status.pack(side="left", padx=12)

        tk.Label(status_bar, text="v7.0", fg=self.MUTED, bg=self.CARD,
                 font=("Segoe UI", 8)).pack(side="right", padx=12)

        self._chamar_dica()

    def _on_focus_in(self, e):
        if self._has_placeholder:
            self.txt_input.delete("1.0", tk.END)
            self.txt_input.config(fg=self.TEXT)
            self._has_placeholder = False
        self._atualizar_contador()

    def _on_focus_out(self, e):
        if not self.txt_input.get("1.0", tk.END).strip():
            self.txt_input.delete("1.0", tk.END)
            self.txt_input.insert("1.0", self._placeholder)
            self.txt_input.config(fg=self.MUTED)
            self._has_placeholder = True

    def _atualizar_contador(self, e=None):
        if self._has_placeholder:
            return
        texto = self.txt_input.get("1.0", tk.END).strip()
        n = len(texto)
        self.char_counter.config(text=f"{n} caracteres")
        if n > 10000:
            self.char_counter.config(fg=self.WARNING)
        elif n > 0:
            self.char_counter.config(fg=self.TEXT_DIM)
        else:
            self.char_counter.config(fg=self.MUTED)

    def _limpar_input(self):
        self.txt_input.delete("1.0", tk.END)
        self.txt_input.insert("1.0", self._placeholder)
        self.txt_input.config(fg=self.MUTED)
        self._has_placeholder = True
        self.char_counter.config(text="0 caracteres", fg=self.MUTED)

    def _chamar_dica(self):
        if not self._has_placeholder:
            return
        dicas = [
            "Dica: Ctrl+Enter para processar",
            "Cole uma petição e clique em INICIAR",
            "Dual: NVIDIA + Gemini (fallback)",
        ]
        import random
        texto = random.choice(dicas)
        self.status.config(text=texto, fg=self.MUTED)
        self.root.after(5000, lambda: self.status.config(
            text="Aguardando petição adversária...", fg=self.MUTED))

    def _carregar_logo(self):
        candidatas = ["logo_dragao.png", "image_30ae89e_clean.png", "image_30ae89e.png"]
        for nome in candidatas:
            path = self._resolver(nome)
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    if img.mode == 'RGBA':
                        bg = Image.new('RGB', img.size, (13, 13, 15))
                        bg.paste(img, mask=img.split()[3])
                        img = bg
                    img.thumbnail((280, 360), Image.LANCZOS)
                    self.photo = ImageTk.PhotoImage(img)
                    tk.Label(self.frame_left, image=self.photo, bg=self.BG).pack(pady=15)
                    return
                except Exception as e:
                    logging.warning('Erro ao carregar logo %s: %s', nome, e)
        self._desenhar_fallback()

    def _resolver(self, path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)

    def _desenhar_fallback(self):
        try:
            w, h = 280, 340
            img = Image.new('RGB', (w, h), (13, 13, 15))
            draw = ImageDraw.Draw(img)
            for i in range(5):
                m = 20 + i * 8
                outline = self.RED if i == 0 else "#1A1A1E" if i == 4 else "#2A2A2E"
                draw.rectangle([m, m, w - m, h - m], outline=outline, width=2 if i == 0 else 1)
            try:
                font_large = ImageFont.truetype("segoeui.ttf", 18)
                font_small = ImageFont.truetype("segoeui.ttf", 10)
            except Exception:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), "INQUISITOR", font=font_large)
            tx = (w - (bbox[2] - bbox[0])) // 2
            draw.text((tx, 120), "INQUISITOR", fill=self.TEXT, font=font_large)
            bbox2 = draw.textbbox((0, 0), "UNIT", font=font_large)
            tx2 = (w - (bbox2[2] - bbox2[0])) // 2
            draw.text((tx2, 150), "UNIT", fill=self.RED, font=font_large)
            bbox3 = draw.textbbox((0, 0), "V.VICTOR DIGITAL FLOW", font=font_small)
            tx3 = (w - (bbox3[2] - bbox3[0])) // 2
            draw.text((tx3, 200), "V.VICTOR DIGITAL FLOW", fill=self.MUTED, font=font_small)
            self.photo = ImageTk.PhotoImage(img)
            tk.Label(self.frame_left, image=self.photo, bg=self.BG).pack(pady=15)
        except Exception:
            f = tk.Frame(self.frame_left, bg=self.BG)
            f.pack(pady=30)
            tk.Label(f, text="⚖", fg=self.RED, bg=self.BG,
                     font=("Segoe UI", 48)).pack()
            tk.Label(f, text="INQUISITOR UNIT",
                     fg=self.RED, bg=self.BG, font=("Segoe UI", 16, "bold")).pack()

    def _pulsar_led(self):
        try:
            cor_atual = self.motor_led.itemcget(self._led, "fill")
            if cor_atual == self.MUTED:
                return
            if cor_atual in (self.SUCCESS, self.GLOW):
                nova = "#2A7A2A" if cor_atual == self.SUCCESS else "#8B1A1A"
            else:
                nova = cor_atual
            self.motor_led.itemconfig(self._led, fill=nova)
            self.root.after(1200, self._pulsar_led)
        except Exception:
            pass

    def _startup_ping(self):
        ok = len(self.llm_manager.motores) > 0
        if ok:
            self.motor_led.itemconfig(self._led, fill=self.WARNING)
            self.status.config(
                text=f"Configurado: {self.llm_manager.motores[0]['nome']} (teste ao processar)",
                fg=self.MUTED)
        else:
            self.motor_led.itemconfig(self._led, fill=self.RED)
            self.status.config(text="Nenhuma chave de API encontrada", fg=self.RED)

    def salvar_no_obsidian(self, conteudo, nome_caso="analise"):
        vault = _CONFIG['obsidian'].get('vault_path', '') or os.path.join(
            os.path.expanduser('~'), 'Documents', 'V_Victor_Digital_Flow', 'Casos')
        try:
            pasta = os.path.join(vault, "Inquisidor")
            os.makedirs(pasta, exist_ok=True)
            agora = datetime.datetime.now()
            nome_arquivo = f"{agora.strftime('%Y-%m-%d')}_{nome_caso.replace(' ', '_').lower()[:40]}.md"
            caminho = os.path.join(pasta, nome_arquivo)

            frontmatter = (
                f"---\n"
                f"title: \"Relatório Jurídico - {nome_caso}\"\n"
                f"date: {agora.strftime('%Y-%m-%d')}\n"
                f"time: {agora.strftime('%H:%M:%S')}\n"
                f"tags:\n"
                f"  - inquisidor\n"
                f"  - relatorio\n"
                f"  - juridico\n"
                f"motor: {self.llm_manager.nomeMotor or 'N/A'}\n"
                f"versao: 7.0\n"
                f"status: analisado\n"
                f"---\n\n"
            )
            rodape = (
                f"\n\n---\n"
                f"*Relatório gerado pelo Inquisidor Jurídico v7.0 — V.victor Digital Flow*\n"
                f"*Motor: {self.llm_manager.nomeMotor or 'N/A'}*\n"
            )

            with open(caminho, "w", encoding="utf-8") as f:
                f.write(frontmatter + conteudo + rodape)

            self.memoria.salvar("ultima_analise", caminho, contexto=nome_caso)
            preview = conteudo[:500].replace('\n', ' ').strip()
            self.memoria.salvar(f"analise_{agora.strftime('%Y%m%d_%H%M%S')}", preview, contexto=nome_caso)
            logging.info('Relatório salvo em %s', caminho)
            return caminho
        except Exception as e:
            logging.error('Erro ao salvar no Obsidian: %s', e)
            return None

    def processar(self):
        if self._has_placeholder:
            texto = ""
        else:
            texto = self.txt_input.get("1.0", tk.END).strip()
        if not texto:
            messagebox.showwarning("Aviso", "Cole a petição adversária para análise.")
            return

        self.btn_analisar.config(state="disabled")
        self.btn_limpar.config(state="disabled")
        self.progresso.pack(side="right")
        self.progresso.start()
        self.motor_led.itemconfig(self._led, fill=self.WARNING)
        self.status.config(text="Inicializando infraestrutura neural...", fg=self.WARNING)
        self.root.update_idletasks()
        logging.info('Processamento iniciado (%d caracteres)', len(texto))

        def _worker():
            try:
                hash_texto = hashlib.sha256(texto.encode('utf-8')).hexdigest()
                cache = self.memoria.carregar_cache(hash_texto)
                if cache:
                    self.root.after(0, lambda: self._mostrar_resultado(cache, "(cache)", None))
                    self.root.after(0, lambda: self.status.config(text="Análise recuperada do cache.", fg=self.SUCCESS))
                    logging.info('Cache hit — resultado reusado')
                    self.root.after(0, self._finalizar)
                    return

                motor, motor_nome = self.llm_manager.obter(
                    status_callback=lambda m: self.root.after(
                        0, lambda m=m: self.status.config(text=m, fg=self.WARNING)))
                if not motor:
                    self.root.after(0, lambda: [
                        messagebox.showerror("Erro", "Todos os motores falharam. Verifique conexão."),
                        self.status.config(text="Erro: infraestrutura indisponível.", fg="red"),
                        self._finalizar()])
                    return

                self.root.after(0, lambda: [
                    self.motor_led.itemconfig(self._led, fill=self.SUCCESS),
                    self.status.config(text=f"Motor ativo: {motor_nome}", fg=self.SUCCESS)])

                self.root.after(0, lambda: self.status.config(
                    text="Fase 0/4: Buscando precedentes reais...", fg=self.WARNING))

                searcher = JurisprudenceSearcher()
                precedentes = searcher.buscar_para_peticao(texto)
                contexto_precedentes = searcher.formatar_contexto(precedentes)
                if contexto_precedentes:
                    logging.info('%d precedentes reais encontrados via busca web', len(precedentes))
                else:
                    logging.info('Nenhum precedente encontrado via busca web')

                memoria_ctx = self.memoria.resumo_memoria()
                prompt_base = self.PROMTPS["analista"]

                prompt_args = {"texto": "{texto}"}
                if contexto_precedentes:
                    prompt_args["precedentes"] = contexto_precedentes
                else:
                    prompt_args["precedentes"] = "Nenhum precedente real foi encontrado automaticamente. NÃO INVENTE precedentes."

                prompt_completo = self.PROMTPS["analista"].format(**prompt_args)
                if memoria_ctx:
                    prompt_completo += f"\n\n{memoria_ctx}"

                CFG = _CONFIG
                MAX_PROMPT = CFG['prompt']['max_chars']
                CHUNK_SIZE = CFG['chunking']['max_size']
                CHUNK_OVERLAP = CFG['chunking']['overlap']

                texto_sanitizado = sanitizar_prompt(texto)

                if len(texto) > CHUNK_SIZE:
                    chunks = _chunk_text(texto_sanitizado, max_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
                    total = len(chunks)
                    self.root.after(0, lambda: self.status.config(
                        text=f"1/4: Analisando {total} blocos em paralelo...", fg=self.RED))
                    analises = [None] * total
                    max_workers = min(CFG.get('parallel', {}).get('max_workers', 4), total)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        fut_map = {}
                        for i, chunk in enumerate(chunks):
                            prompt_chunk = prompt_completo.format(texto=chunk)
                            fut = executor.submit(self.llm_manager._api_call, prompt_chunk)
                            fut_map[fut] = i
                        for fut in concurrent.futures.as_completed(fut_map):
                            idx = fut_map[fut]
                            analises[idx] = fut.result()
                            self.root.after(0, lambda idx=idx, t=total: self.status.config(
                                text=f"1/4: Bloco {idx + 1}/{t} concluído...", fg=self.RED))
                    texto_analise = "\n\n---\n\n".join(analises)
                else:
                    self.root.after(0, lambda: self.status.config(text="1/4: Analisando petição...", fg=self.RED))
                    texto_analise = self.llm_manager._api_call(
                        prompt_completo.format(texto=texto_sanitizado))

                texto_enxuto = texto_analise[:MAX_PROMPT]

                self.root.after(0, lambda: self.status.config(text="2/4: Revisando relatório...", fg=self.RED))
                try:
                    texto_revisado = self.llm_manager._api_call(
                        self.PROMTPS["revisor"].format(relatorio=texto_enxuto))
                except Exception as e:
                    logging.warning('Revisor falhou, usando analista: %s', str(e)[:80])
                    texto_revisado = texto_analise

                texto_enxuto2 = texto_revisado[:MAX_PROMPT]

                self.root.after(0, lambda: self.status.config(text="3/4: Verificando veracidade...", fg=self.RED))
                try:
                    texto_resultado = self.llm_manager._api_call(
                        self.PROMTPS["verificador"].format(relatorio=texto_enxuto2))
                except Exception as e:
                    logging.warning('Verificador falhou, usando revisor: %s', str(e)[:80])
                    texto_resultado = texto_revisado

                self.root.after(0, lambda: self.status.config(text="4/4: Verificando citações na web...", fg=self.RED))
                citacoes = _extrair_citacoes(texto_resultado)
                verificacao = _verificar_citacoes(citacoes, searcher)
                suspeitos = [(t, v) for t, v, s in verificacao if s == 'NÃO VERIFICADO']
                if suspeitos:
                    relatorio_verif = "\n\n---\n## VERIFICAÇÃO DE CITAÇÕES\n"
                    relatorio_verif += "| Tipo | Valor | Status |\n|------|-------|--------|\n"
                    for tipo, valor, status_v in verificacao:
                        relatorio_verif += f"| {tipo} | {valor} | {status_v} |\n"
                    relatorio_verif += (
                        "\n⚠️ **ATENÇÃO**: itens marcados como NÃO VERIFICADO podem não existir. "
                        "Consulte a legislação oficial antes de usar.")
                    texto_resultado += relatorio_verif
                else:
                    texto_resultado += (
                        "\n\n---\n✅ **TODAS AS CITAÇÕES VERIFICADAS** — "
                        "Nenhuma citação suspeita encontrada.")

                if contexto_precedentes:
                    rodape_pre = "\n\n---\n### Precedentes consultados para esta análise\n"
                    for p in precedentes[:8]:
                        rodape_pre += f"- [{p['titulo'][:100]}]({p['url']})\n"
                    texto_resultado += rodape_pre

                self.memoria.salvar_cache(hash_texto, texto_resultado)
                caminho_obs = self.salvar_no_obsidian(texto_resultado)
                self.memoria.registrar_feedback("analise", 5, "Execução bem-sucedida")

                self.root.after(0, lambda: self._mostrar_resultado(texto_resultado, motor_nome, caminho_obs))
                self.root.after(0, lambda: self.status.config(text="Análise concluída.", fg=self.SUCCESS))
                logging.info('Processamento concluído')

            except Exception as e:
                erro = traceback.format_exc()
                logging.error('Erro crítico:\n%s', erro)
                self.root.after(0, lambda: [
                    self.motor_led.itemconfig(self._led, fill=self.RED),
                    messagebox.showerror("Erro", f"{type(e).__name__}: {str(e)[:200]}"),
                    self.status.config(text="Falha crítica.", fg=self.RED)])
            finally:
                self.root.after(0, self._finalizar)

        threading.Thread(target=_worker, daemon=True).start()

    def _finalizar(self):
        self.progresso.stop()
        self.progresso.pack_forget()
        self.btn_analisar.config(state="normal")
        self.btn_limpar.config(state="normal")

    def _mostrar_resultado(self, texto, motor_nome, caminho_obs):
        res_win = tk.Toplevel(self.root)
        res_win.title(f"RELATÓRIO JURÍDICO — {motor_nome}")
        res_win.geometry("960x720")
        res_win.configure(bg=self.BG)
        res_win.minsize(700, 500)

        header = tk.Frame(res_win, bg=self.CARD)
        header.pack(fill="x")
        header_inner = tk.Frame(header, bg=self.CARD)
        header_inner.pack(fill="x", padx=20, pady=(14, 14))

        tk.Label(header_inner, text="RELATÓRIO JURÍDICO",
                 fg=self.RED, bg=self.CARD, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(header_inner, text=f"Motor: {motor_nome}",
                 fg=self.MUTED, bg=self.CARD, font=("Segoe UI", 9)).pack(anchor="w")

        sep_h = tk.Frame(res_win, bg=self.BORDER, height=1)
        sep_h.pack(fill="x", padx=16)

        text_frame = tk.Frame(res_win, bg=self.CARD)
        text_frame.pack(expand=True, fill="both", padx=16, pady=(12, 0))

        out = scrolledtext.ScrolledText(
            text_frame, font=self.FONT_MONO,
            bg="#121214", fg=self.TEXT,
            insertbackground=self.TEXT, relief="flat", padx=16, pady=12,
            highlightthickness=0, borderwidth=0
        )
        out.insert(tk.END, texto)
        out.pack(expand=True, fill="both")
        out.config(state="disabled")

        btn_frame = tk.Frame(res_win, bg=self.BG)
        btn_frame.pack(fill="x", padx=16, pady=(12, 16))

        tk.Button(btn_frame, text="COPIAR",
                  command=lambda: [res_win.clipboard_clear(), res_win.clipboard_append(texto),
                                   self.status.config(text="Relatório copiado!", fg=self.SUCCESS)],
                  bg=self.CARD, fg=self.TEXT, font=self.FONT_BOLD,
                  relief="flat", padx=20, pady=8, cursor="hand2",
                  activebackground=self.BORDER, activeforeground=self.TEXT,
                  borderwidth=0).pack(side="left", padx=(0, 8))

        tk.Button(btn_frame, text="FECHAR", command=res_win.destroy,
                  bg=self.RED, fg="#FFFFFF", font=self.FONT_BOLD,
                  relief="flat", padx=24, pady=8, cursor="hand2",
                  activebackground=self.RED_HOVER, activeforeground="#FFFFFF",
                  borderwidth=0).pack(side="right")

        if caminho_obs:
            self.root.after(100, lambda: messagebox.showinfo("Arquivado", f"Relatório salvo em:\n{caminho_obs}"))


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# ENTRY POINT
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def iniciar():
    try:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        _obter_api_key("NVIDIA_API_KEY", "nvidia")
        _obter_api_key("GOOGLE_API_KEY", "gemini")

        root = tk.Tk()
        app = InquisidorV6(root)
        root.mainloop()
    except ImportError as e:
        logging.critical('Biblioteca ausente: %s', e)
        print(f"[ERRO] Biblioteca ausente: {e}")
        print("Execute: pip install -r requirements.txt")
        traceback.print_exc()
        input("Pressione ENTER...")
    except Exception as e:
        logging.critical('Erro na inicialização: %s', e)
        print(f"[ERRO] Inicialização: {e}")
        traceback.print_exc()
        input("Pressione ENTER...")


if __name__ == "__main__":
    iniciar()
