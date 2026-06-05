import logging
import os
import datetime
import time
import unicodedata
from typing import List
from urllib.parse import urlparse

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Automação Google Forms",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================== VERIFICAÇÃO DE LICENÇA ====================
# Configure aqui a data de vencimento (ANO, MÊS, DIA)
# Exemplo atual: 5 de Julho de 2026 (30 dias)
DATA_EXPIRACAO = datetime.date(2026, 6, 15)
DATA_ATUAL = datetime.date.today()

if DATA_ATUAL > DATA_EXPIRACAO:
    st.error("🔒 **Acesso Expirado!**")
    st.warning(f"Sua licença venceu no dia {DATA_EXPIRACAO.strftime('%d/%m/%Y')}. Por favor, entre em contato para renovar o acesso mensal.")
    st.stop()  # Isso impede que o restante do site carregue

# ==================== CSS CUSTOMIZADO ====================
st.markdown("""
<style>
    .stTextArea textarea { font-family: monospace; font-size: 0.82rem; }
    .log-box { background: #0e1117; color: #00ff88; font-family: monospace;
               font-size: 0.80rem; padding: 12px; border-radius: 8px;
               max-height: 350px; overflow-y: auto; white-space: pre-wrap; }
    .metric-success { color: #00c853; font-weight: bold; }
    .metric-error   { color: #ff5252; font-weight: bold; }
    .rota-tag { display: inline-block; background: #1e3a5f; color: #90caf9;
                border-radius: 4px; padding: 2px 8px; margin: 2px;
                font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

# ==================== CONSTANTES ====================
TIMEOUT_PADRAO = 15
TIMEOUT_ENVIO = 20
INTERVALO_ENTRE_ENVIOS = 3
MAX_TENTATIVAS = 2
INTERVALO_RETRY = 2

BAIRROS_DEFAULT = [
    "Aerolândia", "Aeroporto", "Aldeota", "Alto da Balança", "Amadeu Furtado", 
    "Ancuri", "Antônio Bezerra", "Autran Nunes", "Barra do Ceará", "Barroso", 
    "Bela Vista", "Benfica", "Bom Futuro", "Bom Jardim", "Bonsucesso", 
    "Cais do Porto", "Cambeba", "Canindezinho", "Carlito Pamplona", "Castelão", 
    "Centro", "Cidade dos Funcionários", "Cidade Nova", "Coaçu", "Cocó", 
    "Conjunto Ceará I", "Conjunto Ceará II", "Conjunto Esperança", "Couto Fernandes", "Curió", 
    "Damas", "De Lourdes", "Dias Macedo", "Dom Lustosa", "Edson Queiroz", 
    "Engenheiro Luciano Cavalcante", "Farias Brito", "Fátima", "Floresta", "Genibaú", 
    "Granja Lisboa", "Granja Portugal", "Guajeru", "Guararapes", "Henrique Jorge", 
    "Itaoca", "Itaperi", "Jacarecanga", "Jangurussu", "Jardim América", 
    "Jardim Cearense", "Jardim das Oliveiras", "Jardim Iracema", "José Bonifácio", "José de Alencar", 
    "Manuel Sátiro", "Maraponga", "Meireles", "Messejana", "Mondubim", 
    "Monte Castelo", "Montese", "Moura Brasil", "Mucuripe", "Novo Mondubim", 
    "Olavo Bilac", "Panamericano", "Papicu", "Parangaba", "Parque Araxá", 
    "Parque Dois Irmãos", "Parque Iracema", "Parque Manibura", "Parque Presidente Vargas", "Parque Santa Maria", 
    "Parque Santa Rosa", "Parquelândia", "Parreão", "Passaré", "Paupina", 
    "Pedras", "Pici", "Pirambu", "Planalto Ayrton Senna", "Praia de Iracema", 
    "Praia do Futuro", "Prefeito José Walter", "Quintino Cunha", "Rodolfo Teófilo", "Sabiaguaba", 
    "Salinas", "Santa Maria", "Santa Rosa", "São Bento", "São Gerardo", 
    "São João do Tauape", "Sapiranga/Coité", "Serrinha", "Siqueira", "Varjota", 
    "Vicente Pinzón", "Vila Ellery", "Vila Manoel Sátiro", "Vila Peri", "Vila União", 
    "Vila Velha"
]

BAIRROS_PREFERIDOS_DEFAULT = [
    "Parque Iracema", "Cajazeiras", "Cambeba", "Damas",
    "Itaperi", "Guararapes", "Luciano Cavalcante"
]

# ==================== SESSION STATE ====================
def init_state():
    defaults = {
        "rotas_disponiveis": [],
        "rotas_selecionadas": [],
        "resultado": {},
        "logs": [],
        "fase": "idle",  # idle | mapeado | enviando | concluido
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ==================== LOGGING PARA STREAMLIT ====================
def make_log_fn(placeholder):
    """Retorna uma função de log que atualiza o placeholder em tempo real."""
    def log(msg: str, nivel: str = "INFO"):
        if nivel == "DEBUG":
            return
        icons = {"INFO": "ℹ️", "OK": "✅", "ERRO": "❌", "WARN": "⚠️",
                 "PROC": "⚙️", "RETRY": "🔁", "WAIT": "⏳", "MAP": "🗺️"}
        icon = icons.get(nivel, "•")
        entry = f"{icon} {msg}"
        st.session_state.logs.append(entry)
        content = "\n".join(st.session_state.logs[-100:])  # Últimas 100 linhas
        placeholder.markdown(f'<div class="log-box">{content}</div>', unsafe_allow_html=True)
    return log

# ==================== FUNÇÕES AUXILIARES ====================
def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()


def validar_url(url: str) -> bool:
    try:
        result = urlparse(url)
        if not result.scheme or not result.netloc:
            return False
        if "docs.google.com/forms" not in url and "forms.gle" not in url:
            return False
        return True
    except Exception:
        return False


def safe_click(driver: webdriver.Chrome, element) -> None:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.3)
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def xpath_literal(texto: str) -> str:
    if "'" not in texto:
        return f"'{texto}'"
    if '"' not in texto:
        return f'"{texto}"'
    partes = texto.split("'")
    return "concat(" + ", \"'\", ".join(f"'{parte}'" for parte in partes) + ")"


def _elementos_editaveis_visiveis(root) -> List:
    elementos = root.find_elements(
        By.XPATH,
        ".//textarea | .//input[(@type='text' or @type='number') and not(@type='hidden')]",
    )
    return [el for el in elementos if el.is_displayed()]


def _preencher_elemento(driver, elemento, texto: str) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
    time.sleep(0.2)

    tag = (elemento.tag_name or "").lower()
    if tag == "textarea":
        try:
            elemento.clear()
        except Exception:
            pass
        driver.execute_script("arguments[0].value = arguments[1];", elemento, texto)
    else:
        driver.execute_script("arguments[0].focus();", elemento)
        driver.execute_script("arguments[0].value = '';", elemento)
        driver.execute_script("arguments[0].value = arguments[1];", elemento, texto)

    driver.execute_script("""
        var el = arguments[0];
        ['input', 'change', 'blur'].forEach(function(evtName) {
            el.dispatchEvent(new Event(evtName, { bubbles: true }));
        });
    """, elemento)


def preencher_input_por_html(driver, wait, indice: int, texto: str) -> None:
    """Fallback baseado na estrutura visível do HTML da página."""
    wait.until(lambda d: len(_elementos_editaveis_visiveis(d)) > indice)
    elementos = _elementos_editaveis_visiveis(driver)

    if len(elementos) <= indice:
        raise IndexError(
            f"Não foi possível localizar o campo HTML de índice {indice}. "
            f"Encontrados {len(elementos)} elementos editáveis visíveis."
        )

    _preencher_elemento(driver, elementos[indice], texto)


def preencher_input_por_pergunta(driver, wait, pergunta: str, texto: str) -> None:
    """Localiza o input associado ao texto da pergunta e preenche o campo."""
    bloco_xpath = (
        f"//div[@jsmodel='CP1oW'][.//*[self::span or self::div or self::label]"
        f"[contains(normalize-space(.), {xpath_literal(pergunta)})]]"
    )

    try:
        container = wait.until(EC.presence_of_element_located((By.XPATH, bloco_xpath)))
    except Exception:
        container = None

    if container is None:
        pergunta_xpath = (
            f"//*[self::span or self::div or self::label][contains(normalize-space(.), {xpath_literal(pergunta)})]"
        )
        pergunta_element = wait.until(EC.presence_of_element_located((By.XPATH, pergunta_xpath)))

        try:
            container = pergunta_element.find_element(
                By.XPATH,
                "./ancestor::div[@jsmodel='CP1oW'][1]",
            )
        except Exception:
            container = pergunta_element

    inputs = _elementos_editaveis_visiveis(container)

    if not inputs:
        inputs = _elementos_editaveis_visiveis(driver)

    if not inputs:
        raise IndexError(f"Não foi possível localizar o campo da pergunta: {pergunta}")

    _preencher_elemento(driver, inputs[0], texto)


def preencher_input(driver, wait, index: int, texto: str) -> None:
    """Fallback antigo mantido para páginas que ainda usem ordem simples dos inputs."""
    xpath_inputs = "//textarea | //input[(@type='text' or @type='number') and not(@type='hidden')]"

    wait.until(
        lambda d: len([el for el in d.find_elements(By.XPATH, xpath_inputs) if el.is_displayed()]) > index
    )
    inputs = [el for el in driver.find_elements(By.XPATH, xpath_inputs) if el.is_displayed()]

    if len(inputs) <= index:
        raise IndexError(
            f"Não foi possível localizar o input de índice {index}. "
            f"Encontrados {len(inputs)} inputs visíveis."
        )

    _preencher_elemento(driver, inputs[index], texto)


def ordenar_rotas_por_preferencia(rotas: List[str], bairros_preferidos: List[str]) -> List[str]:
    bairros_pref_norm = {remover_acentos(b): b for b in bairros_preferidos}
    rotas_preferidas, rotas_restantes = [], []
    for rota in rotas:
        rota_norm = remover_acentos(rota)
        encontrou = False
        for bp_norm, bp_orig in bairros_pref_norm.items():
            if bp_norm in rota_norm:
                rotas_preferidas.append((bairros_preferidos.index(bp_orig), rota))
                encontrou = True
                break
        if not encontrou:
            rotas_restantes.append(rota)
    rotas_preferidas.sort(key=lambda x: x[0])
    return [r for _, r in rotas_preferidas] + rotas_restantes

# ==================== SELENIUM ====================
def criar_driver() -> webdriver.Chrome:
    """
    Cria o ChromeDriver com suporte a ambiente local e Streamlit Cloud.
    Headless é sempre ativado (obrigatório em ambiente cloud/server).
    """
    options = webdriver.ChromeOptions()

    # ── Modo headless ─────────────────────────────────────────────────────────
    options.add_argument("--headless=new")

    # ── Flags essenciais para ambientes container / cloud ─────────────────────
    options.add_argument("--no-sandbox")               # Sem sandbox do kernel
    options.add_argument("--disable-setuid-sandbox")   # Sandbox extra desativada
    options.add_argument("--disable-dev-shm-usage")    # Usa /tmp em vez de /dev/shm

    # ── GPU / renderização (desabilitar para estabilidade) ────────────────────
    options.add_argument("--disable-gpu")

    # ── Janela padrão ─────────────────────────────────────────────────────────
    options.add_argument("--window-size=1920,1080")
    
    # ── Estabilidade em container / headless ──────────────────────────────────
    options.add_argument("--disable-blink-features=AutomationControlled")  # Evita detecção
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--no-first-run")              # Skip first-run tasks
    options.add_argument("--no-default-browser-check")  # Skip browser check
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--disable-client-side-phishing-detection")

    # Tenta encontrar Chrome/Chromium instalado no sistema
    CHROME_PATHS = [
        "/usr/bin/chromium",           # Streamlit Cloud (Debian)
        "/usr/bin/chromium-browser",   # Outras distribuições
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",          # Snap packages
    ]
    
    CHROMEDRIVER_PATHS = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
    ]

    # Detecta Chrome/Chromium disponível
    chrome_path = next((p for p in CHROME_PATHS if os.path.exists(p)), None)
    chromedriver_path = next((p for p in CHROMEDRIVER_PATHS if os.path.exists(p)), None)

    if chrome_path:
        options.binary_location = chrome_path
        logging.info(f"Chrome encontrado em: {chrome_path}")

    # Tenta criar driver com o que está disponível
    try:
        if chromedriver_path:
            # Usar chromedriver explícito se encontrado
            return webdriver.Chrome(service=Service(chromedriver_path), options=options)
        else:
            # Deixar Selenium encontrar automaticamente ou usar webdriver-manager
            return webdriver.Chrome(options=options)
    except Exception as e:
        # Fallback: tentar com webdriver-manager
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except Exception as e2:
            raise RuntimeError(
                f"❌ Não foi possível inicializar o ChromeDriver.\n"
                f"Erro 1: {e}\n"
                f"Erro 2: {e2}\n\n"
                f"📝 Solução para Streamlit Cloud:\n"
                f"  1. Certifique-se que packages.txt contém 'chromium' e 'chromium-driver'\n"
                f"  2. Clique em 'Redeploy' (não apenas reload)\n"
                f"  3. Aguarde a instalação completar\n\n"
                f"💻 Solução Local:\n"
                f"  1. Instale Google Chrome\n"
                f"  2. Adicione webdriver-manager em requirements.txt"
            )


def obter_rotas_disponiveis(
    url: str, nome: str, id_func: str,
    meus_bairros: List[str], log
) -> List[str]:
    driver = None
    try:
        log("Iniciando ChromeDriver para mapeamento...", "MAP")
        driver = criar_driver()
        log("✅ ChromeDriver iniciado", "MAP")
        
        wait = WebDriverWait(driver, TIMEOUT_PADRAO)
        rotas_encontradas = []
        bairros_limpos = [remover_acentos(b) for b in meus_bairros]

        log(f"Navegando para: {url[:50]}...", "MAP")
        driver.get(url)
        log("✅ Página carregada", "MAP")
        
        time.sleep(1)
        log("Aguardando inputs de identificação...", "MAP")
        
        try:
            preencher_input_por_pergunta(driver, wait, "Qual seu nome?", nome)
            log(f"✅ Nome preenchido: {nome}", "MAP")
        except Exception as e:
            log(f"⚠️ Erro ao preencher nome: {str(e)[:80]}", "AVISO")
            raise
        
        try:
            preencher_input_por_pergunta(driver, wait, "Qual seu ID?", id_func)
            log(f"✅ ID preenchido: {id_func}", "MAP")
        except Exception as e:
            log(f"⚠️ Erro ao preencher ID: {str(e)[:80]}", "AVISO")
            raise
        
        time.sleep(1)
        log("Procurando botão 'Avançar'...", "MAP")
        
        # Múltiplos XPaths para localizar o botão (PT e EN)
        xpath_variants = [
            "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima' or normalize-space(text())='Next']",
            "//button//span[contains(text(), 'Avançar') or contains(text(), 'Próxima') or contains(text(), 'Next')]",
            "//span[contains(text(), 'Avançar') or contains(text(), 'Próxima') or contains(text(), 'Next')]",
            "//*[normalize-space(text())='Avançar' or normalize-space(text())='Próxima' or normalize-space(text())='Next']"
        ]
        
        btn = None
        for idx, xpath in enumerate(xpath_variants):
            try:
                log(f"  Tentando XPath {idx+1}/{len(xpath_variants)}...", "DEBUG")
                elements = driver.find_elements(By.XPATH, xpath)
                if elements:
                    log(f"  ✅ Encontrou {len(elements)} elemento(s) com XPath {idx+1}", "DEBUG")
                    btn = elements[0]
                    break
                else:
                    log(f"  ❌ XPath {idx+1} retornou 0 elementos", "DEBUG")
            except Exception as ex:
                log(f"  ⚠️ XPath {idx+1} error: {str(ex)[:60]}", "DEBUG")
                continue
        
        if not btn:
            # Debugging: listar todos os spans na página
            all_spans = driver.find_elements(By.TAG_NAME, "span")
            log(f"⚠️ Botão não encontrado. Existem {len(all_spans)} spans na página.", "DEBUG")
            for i, span in enumerate(all_spans[:10]):
                try:
                    text = span.text.strip()
                    if text:
                        log(f"  Span {i}: '{text[:40]}'", "DEBUG")
                except:
                    pass
            raise Exception("Botão 'Avançar/Next' não localizado em nenhum XPath")
        
        try:
            log("✅ Botão 'Avançar/Next' localizado", "MAP")
            # Scroll até o botão
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
            safe_click(driver, btn)
            log("✅ Avançou para página 2 (seleção de rota)", "MAP")
        except Exception as e:
            log(f"⚠️ Erro ao clicar no botão: {str(e)[:80]}", "AVISO")
            raise

        time.sleep(2)
        log("Aguardando dropdown de rotas...", "MAP")
        
        try:
            dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
            log("✅ Dropdown localizado", "MAP")
            safe_click(driver, dropdown)
            log("✅ Dropdown clicado", "MAP")
        except Exception as e:
            log(f"⚠️ Erro com dropdown: {str(e)[:80]}", "AVISO")
            raise
            
        time.sleep(2)
        log("Extraindo opções do dropdown...", "MAP")
        
        try:
            opcoes = driver.find_elements(By.XPATH, "//div[@role='option']")
            log(f"✅ Total de opções encontradas: {len(opcoes)}", "MAP")
        except Exception as e:
            log(f"⚠️ Erro ao extrair opções: {str(e)[:80]}", "AVISO")
            raise

        for idx, opt in enumerate(opcoes):
            try:
                texto_original = opt.get_attribute("data-value") or opt.text
                if texto_original and texto_original != "Escolher":
                    texto_limpo = remover_acentos(texto_original)
                    if any(b in texto_limpo for b in bairros_limpos):
                        rotas_encontradas.append(texto_original)
                        log(f"✅ Rota {len(rotas_encontradas)}: {texto_original}", "OK")
            except Exception as e:
                log(f"⚠️ Erro ao processar opção {idx}: {str(e)[:60]}", "AVISO")
                continue

        log(f"Mapeamento concluído — {len(rotas_encontradas)} rota(s) compatível(is)", "INFO")
        return rotas_encontradas

    except Exception as e:
        log(f"❌ Erro no mapeamento: {str(e)[:120]}", "ERRO")
        import traceback
        log(f"Stacktrace: {traceback.format_exc()[:200]}", "DEBUG")
        return []
    finally:
        if driver:
            try:
                driver.quit()
                log("✅ ChromeDriver fechado", "DEBUG")
            except:
                pass


def enviar_formulario(
    url: str, rota: str, nome: str, id_func: str, telefone: str,
    log, tentativa: int = 1
) -> bool:
    driver = None
    try:
        log(f"[Tentativa {tentativa}/{MAX_TENTATIVAS}] Iniciando envio: {rota}", "PROC")
        driver = criar_driver()
        log("  ✅ ChromeDriver criado", "DEBUG")
        
        wait = WebDriverWait(driver, TIMEOUT_ENVIO)

        log("  Navegando para formulário...", "DEBUG")
        driver.get(url)
        time.sleep(1)
        log("  ✅ Página carregada", "DEBUG")

        # Página 1: Identificação
        log("  Preenchendo página 1 (identificação)...", "DEBUG")
        preencher_input_por_pergunta(driver, wait, "Qual seu nome?", nome)
        log(f"    ✅ Nome: {nome}", "DEBUG")
        
        preencher_input_por_pergunta(driver, wait, "Qual seu ID?", id_func)
        log(f"    ✅ ID: {id_func}", "DEBUG")
        
        log("  Clicando botão Avançar (página 1)...", "DEBUG")
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima' or normalize-space(text())='Next']")
        ))
        safe_click(driver, btn)
        log("  ✅ Avançado para página 2", "DEBUG")

        # Página 2: Seleção da Rota
        time.sleep(2)
        log("  Selecionando rota na página 2...", "DEBUG")
        
        dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
        log("    ✅ Dropdown encontrado", "DEBUG")
        
        safe_click(driver, dropdown)
        time.sleep(1)
        log("    ✅ Dropdown aberto", "DEBUG")
        
        opcao = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//div[@role='option']//span[text()='{rota}']")
        ))
        log(f"    ✅ Opção '{rota}' localizada", "DEBUG")
        
        safe_click(driver, opcao)
        time.sleep(1)
        log(f"    ✅ Opção '{rota}' selecionada", "DEBUG")
        
        log("  Clicando botão Avançar (página 2)...", "DEBUG")
        btn2 = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima' or normalize-space(text())='Next']")
        ))
        safe_click(driver, btn2)
        log("  ✅ Avançado para página 3", "DEBUG")

        # Página 3: Telefone + Envio
        time.sleep(2)
        log("  Preenchendo página 3 (telefone)...", "DEBUG")
        
        preencher_input(driver, wait, 0, telefone)
        log(f"    ✅ Telefone: {telefone}", "DEBUG")
        
        log("  Clicando botão Enviar...", "DEBUG")
        btn_enviar = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//span[normalize-space(text())='Enviar' or normalize-space(text())='Submit']")
        ))
        safe_click(driver, btn_enviar)
        log("  ✅ Formulário enviado (clique realizado)", "DEBUG")
        
        # Aguarda um pouco para garantir que o envio foi processado
        time.sleep(2)
        log(f"✅ SUCESSO: {rota}", "OK")
        return True

    except Exception as e:
        log(f"❌ Falha no envio de '{rota}': {str(e)[:100]}", "ERRO")
        import traceback
        log(f"   Stacktrace: {traceback.format_exc()[:150]}", "DEBUG")
        
        if tentativa < MAX_TENTATIVAS:
            log(f"🔁 Aguardando {INTERVALO_RETRY}s antes de retry...", "RETRY")
            time.sleep(INTERVALO_RETRY)
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                driver = None
            return enviar_formulario(url, rota, nome, id_func, telefone, log, tentativa + 1)
        return False
    finally:
        if driver:
            try:
                driver.quit()
                log("  ✅ ChromeDriver fechado", "DEBUG")
            except:
                pass

# ==================== INTERFACE STREAMLIT ====================

# ── Sidebar: Credenciais ──────────────────────────────────────
with st.sidebar:
    st.title("📋 Automação Forms")
    
    dias_restantes = (DATA_EXPIRACAO - DATA_ATUAL).days
    if dias_restantes <= 5:
        st.warning(f"⚠️ Licença expira em {dias_restantes} dias.")
    else:
        st.success(f"✅ Licença ativa: {dias_restantes} dias restantes.")
        
    st.divider()

    st.subheader("👤 Dados do Funcionário")
    nome_input    = st.text_input("Nome completo", value="Thiago Bezerra", disabled=True, placeholder="Ex: João Silva",
                                   help="Preenchido no campo Nome do formulário")
    id_input      = st.text_input("ID do Funcionário", value="2359946", disabled=True, placeholder="Ex: 12345")
    telefone_input = st.text_input("Telefone", value="85988299118", disabled=True, placeholder="Ex: 85999999999")

    st.divider()
    st.subheader("⚙️ Configurações Avançadas")

    with st.expander("Timeouts & Intervalos"):
        timeout_p   = st.number_input("Timeout padrão (s)", value=TIMEOUT_PADRAO, min_value=5)
        timeout_e   = st.number_input("Timeout envio (s)", value=TIMEOUT_ENVIO, min_value=5)
        intervalo   = st.number_input("Intervalo entre envios (s)", value=INTERVALO_ENTRE_ENVIOS, min_value=1)
        max_tent    = st.number_input("Máx. tentativas por rota", value=MAX_TENTATIVAS, min_value=1, max_value=5)

    st.divider()
    st.caption("Automação headless via Selenium · Chromium")

# ── Main ──────────────────────────────────────────────────────
st.title("📋 Automação Google Forms")
st.markdown("Preenche e envia formulários de escala automaticamente com base nos bairros configurados.")

# ── URL ───────────────────────────────────────────────────────
url_input = st.text_input(
    "🔗 URL do Formulário Google",
    placeholder="https://docs.google.com/forms/d/e/.../viewform",
    label_visibility="visible"
)

# ── Configuração de Bairros ───────────────────────────────────
with st.expander("🏘️ Configuração de Bairros", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Meus Bairros** *(um por linha)*")
        bairros_txt = st.text_area(
            "meus_bairros", label_visibility="hidden",
            value="\n".join(BAIRROS_DEFAULT), height=220,
            help="Bairros que você atende. O formulário será enviado apenas para rotas que contenham esses bairros."
        )
    with col_b:
        st.markdown("**Ordem de Preferência** *(um por linha)*")
        pref_txt = st.text_area(
            "bairros_pref", label_visibility="hidden",
            value="\n".join(BAIRROS_PREFERIDOS_DEFAULT), height=220,
            help="Bairros mais prioritários ficam no topo. Os demais ficam ao final da fila."
        )

meus_bairros   = [b.strip() for b in bairros_txt.splitlines() if b.strip()]
bairros_pref   = [b.strip() for b in pref_txt.splitlines() if b.strip()]

st.divider()

# ── Fase 1: Mapear Rotas ──────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 4])

with col1:
    btn_mapear = st.button("🗺️ Mapear Rotas", use_container_width=True, type="secondary")

with col2:
    btn_limpar = st.button("🔄 Limpar", use_container_width=True)

if btn_limpar:
    st.session_state.rotas_disponiveis = []
    st.session_state.rotas_selecionadas = []
    st.session_state.resultado = {}
    st.session_state.logs = []
    st.session_state.fase = "idle"
    st.rerun()

# Validações antes de mapear
if btn_mapear:
    erros = []
    if not nome_input.strip():    erros.append("Nome do funcionário")
    if not id_input.strip():      erros.append("ID do funcionário")
    if not telefone_input.strip(): erros.append("Telefone")
    if not url_input.strip():     erros.append("URL do formulário")
    elif not validar_url(url_input.strip()):
        erros.append("URL inválida (deve ser docs.google.com/forms ou forms.gle)")

    if erros:
        st.error("Preencha os campos obrigatórios: " + " · ".join(erros))
    else:
        st.session_state.logs = []
        st.session_state.rotas_disponiveis = []
        st.session_state.fase = "mapeando"

        log_placeholder = st.empty()
        log = make_log_fn(log_placeholder)

        with st.spinner("Mapeando rotas disponíveis no formulário..."):
            rotas = obter_rotas_disponiveis(
                url_input.strip(), nome_input.strip(),
                id_input.strip(), meus_bairros, log
            )

        if rotas:
            rotas_ord = ordenar_rotas_por_preferencia(rotas, bairros_pref)
            st.session_state.rotas_disponiveis = rotas_ord
            st.session_state.rotas_selecionadas = rotas_ord.copy()
            st.session_state.fase = "mapeado"
            st.rerun()
        else:
            st.session_state.fase = "idle"
            st.warning("Nenhuma rota compatível encontrada. Verifique a lista de bairros.")

# ── Exibir rotas mapeadas + seleção ───────────────────────────
if st.session_state.fase in ("mapeado", "concluido") and st.session_state.rotas_disponiveis:
    st.success(f"✅ {len(st.session_state.rotas_disponiveis)} rota(s) encontrada(s)")

    st.markdown("#### Selecione as rotas para envio:")
    selecionadas = []
    cols = st.columns(2)
    for i, rota in enumerate(st.session_state.rotas_disponiveis):
        status_icon = ""
        if rota in st.session_state.resultado:
            status_icon = " ✅" if st.session_state.resultado[rota] else " ❌"
        checked = st.session_state.resultado.get(rota) is None  # Desmarca as que já foram processadas
        with cols[i % 2]:
            if st.checkbox(rota + status_icon, value=checked, key=f"rota_{i}"):
                selecionadas.append(rota)

    st.session_state.rotas_selecionadas = selecionadas

    st.divider()

    # ── Fase 2: Enviar Formulários ────────────────────────────
    btn_enviar = st.button(
        f"🚀 Enviar {len(selecionadas)} Formulário(s)",
        type="primary", use_container_width=False,
        disabled=len(selecionadas) == 0
    )

    if btn_enviar:
        if not nome_input.strip() or not id_input.strip() or not telefone_input.strip():
            st.error("Credenciais incompletas na barra lateral.")
        else:
            st.session_state.logs = []
            st.session_state.resultado = {}
            st.session_state.fase = "enviando"

            log_placeholder = st.empty()
            log = make_log_fn(log_placeholder)

            progresso = st.progress(0, text="Iniciando envios...")
            total = len(selecionadas)
            sucesso_count, falha_count = 0, 0

            for idx, rota in enumerate(selecionadas, 1):
                progresso.progress(
                    (idx - 1) / total,
                    text=f"[{idx}/{total}] Enviando: {rota}"
                )
                log(f"[{idx}/{total}] Processando: {rota}", "PROC")

                ok = enviar_formulario(
                    url_input.strip(), rota,
                    nome_input.strip(), id_input.strip(), telefone_input.strip(),
                    log
                )
                st.session_state.resultado[rota] = ok

                if ok:
                    sucesso_count += 1
                else:
                    falha_count += 1

                if idx < total:
                    log(f"Aguardando {intervalo}s até próximo envio...", "WAIT")
                    time.sleep(intervalo)

            progresso.progress(1.0, text="Concluído!")
            st.session_state.fase = "concluido"

            # Resumo final
            st.divider()
            st.subheader("📊 Resumo Final")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Enviado", total)
            c2.metric("✅ Sucessos", sucesso_count)
            c3.metric("❌ Falhas", falha_count)

            if falha_count == 0:
                st.success("Todos os formulários foram enviados com sucesso! 🎉")
            elif sucesso_count == 0:
                st.error("Nenhum formulário foi enviado com sucesso. Verifique os logs.")
            else:
                st.warning(f"{sucesso_count} enviado(s) com sucesso, {falha_count} com falha.")

# ── Log persistente (após execução) ──────────────────────────
if st.session_state.logs and st.session_state.fase not in ("enviando",):
    with st.expander("📄 Ver Logs da Última Execução", expanded=False):
        content = "\n".join(st.session_state.logs)
        st.markdown(f'<div class="log-box">{content}</div>', unsafe_allow_html=True)
        st.download_button(
            "⬇️ Baixar logs (.txt)",
            data="\n".join(st.session_state.logs),
            file_name="automacao_forms.log",
            mime="text/plain"
        )