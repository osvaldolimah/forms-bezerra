import logging
import os
import time
import unicodedata
from typing import List
from urllib.parse import urlparse

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ==================== CONFIGURAÇÃO DE LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automacao_forms.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# ==================== CARREGAMENTO DE VARIÁVEIS DE AMBIENTE ====================
load_dotenv()

NOME = os.getenv("NOME_FUNCIONARIO", "").strip()
ID_FUNC = os.getenv("ID_FUNCIONARIO", "").strip()

if not all([NOME, ID_FUNC]):
    logger.error("[ERRO] Variaveis de ambiente nao configuradas. Crie um arquivo .env com NOME_FUNCIONARIO e ID_FUNCIONARIO")
    exit(1)

# ==================== DADOS ====================
MEUS_BAIRROS = [
    "Aerolândia", "Aeroporto", "Aldeota", "Alto da Balança", "Álvaro Weyne",
        "Amadeu Furtado", "Ancuri", "Antônio Bezerra", "Autran Nunes", "Barra do Ceará",
        "Barroso", "Bela Vista", "Benfica", "Boa Vista", "Bom Futuro",
        "Bom Jardim", "Bonsucesso", "Cais do Porto", "Cajazeiras", "Cambeba",
        "Canindezinho", "Carlito Pamplona", "Castelão", "Centro", "Cidade 2000",
        "Cidade dos Funcionários", "Coaçu", "Conjunto Ceará I", "Conjunto Ceará II", "Conjunto Esperança",
        "Conjunto Palmeiras", "Couto Fernandes", "Cristo Redentor", "Curió", "Damas",
        "De Lourdes", "Demócrito Rocha", "Dendê", "Dias Macedo", "Dionísio Torres",
        "Dom Lustosa", "Edson Queiroz", "Engenheiro Luciano Cavalcante", "Farias Brito", "Fatima",
        "Floresta", "Genibaú", "Granja Lisboa", "Granja Portugal", "Guajerú",
        "Guararapes", "Henrique Jorge", "Itaoca", "Itaperi", "Jacarecanga",
        "Jangurussu", "Jardim America", "Jardim Cearense", "Jardim das Oliveiras", "Jardim Guanabara",
        "João XXIII", "Joaquim Távora", "Jóquei Clube", "José de Alencar", "Lagoa Redonda",
        "Manuel Dias Branco", "Manoel Sátiro", "Maraponga", "Meireles", "Messejana",
        "Mondubim", "Montese", "Moura Brasil", "Mucuripe", "Novo Mondubim",
        "Olavo Oliveira", "Padre Andrade", "Panamericano", "Papicu", "Parque Araxá",
        "Parque Dois Irmãos", "Parque 2 irmãos", "Parque Manibura", "Parque Santa Rosa", "Parque São José",
        "Parquelândia", "Parreão", "Passaré", "Paupina", "Pedras",
        "Pici", "Pirambu", "Planalto Ayrton Senna", "Praia de Iracema", "Praia do Futuro I",
        "Praia do Futuro II", "Prefeito José Walter", "Quintino Cunha", "Rodolfo Teófilo", "Sabiaguaba",
        "Salinas", "Santa Maria", "São Bento", "São Gerardo", "São João do Tauape",
        "Serrinha", "Siqueira", "Varjota", "Vicente Pinzón", "Vila Ellery",
        "Vila União", "Vila Velha", "Parque Iracema", "Cocó"
]

BAIRROS_PREFERIDOS = [
    "Serrinha", "Pici", "Bela Vista", "Jardim America",
        "Itaperi", "Fatima", "Vila União", "Bom Futuro", "Dias Macedo", "Parreão",
        "Parque Dois Irmãos", "Parque 2 irmãos", "Benfica", "Damas", "Panamericano"
]

TIMEOUT_PADRAO = 15
TIMEOUT_ENVIO = 20
INTERVALO_ENTRE_ENVIOS = 3
MAX_TENTATIVAS = 2
INTERVALO_RETRY = 2

# ==================== FUNÇÕES AUXILIARES ====================

def ordenar_rotas_por_preferencia(rotas: List[str]) -> List[str]:
    rotas_preferidas = []
    rotas_restantes = []
    
    bairros_pref_normalizados = {remover_acentos(b): b for b in BAIRROS_PREFERIDOS}
    
    for rota in rotas:
        rota_normalizada = remover_acentos(rota)
        encontrou_preferido = False
        for bairro_pref_norm, bairro_pref_original in bairros_pref_normalizados.items():
            if bairro_pref_norm in rota_normalizada:
                rotas_preferidas.append((BAIRROS_PREFERIDOS.index(bairro_pref_original), rota))
                encontrou_preferido = True
                break
        
        if not encontrou_preferido:
            rotas_restantes.append(rota)
    
    rotas_preferidas.sort(key=lambda x: x[0])
    resultado = [rota for _, rota in rotas_preferidas] + rotas_restantes
    
    return resultado


def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()


def validar_url(url: str) -> bool:
    try:
        result = urlparse(url)
        if not result.scheme or not result.netloc:
            logger.error(f"URL inválida: {url}")
            return False
        
        if "docs.google.com/forms" not in url and "forms.gle" not in url:
            logger.warning(f"URL nao parece ser um formulario Google: {url}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Erro ao validar URL: {e}")
        return False


def safe_click(driver: webdriver.Chrome, element) -> None:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.3)
        element.click()
    except Exception as e:
        logger.debug(f"Click padrao falhou, usando JavaScript: {e}")
        try:
            driver.execute_script("arguments[0].click();", element)
        except Exception as js_error:
            logger.error(f"[ERRO] Falha ao clicar no elemento: {js_error}")
            raise


def preencher_input_por_pergunta(driver: webdriver.Chrome, wait: WebDriverWait, pergunta: str, valor: str) -> None:
    """
    Preenche um campo de texto baseado no texto da pergunta.
    Procura o container da pergunta (role=listitem) e depois o input dentro dele.
    """
    xpath_container = f'//div[@role="listitem" and contains(., "{pergunta}")]'
    
    container = wait.until(EC.presence_of_element_located((By.XPATH, xpath_container)))
    
    input_el = container.find_element(By.XPATH, './/input[@type="text"]')
    
    safe_click(driver, input_el)
    input_el.clear()
    driver.execute_script("arguments[0].value = arguments[1];", input_el, valor)
    driver.execute_script("""
        var el = arguments[0];
        ['input', 'change', 'blur'].forEach(function(evtName) {
            el.dispatchEvent(new Event(evtName, { bubbles: true }));
        });
    """, input_el)
    logger.debug(f"Preenchido '{pergunta}': {valor}")


def criar_driver() -> webdriver.Chrome:
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-logging")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        logger.debug("[OK] ChromeDriver criado com sucesso")
        return driver
    except Exception as e:
        logger.error(f"[ERRO] Erro ao criar ChromeDriver: {e}")
        raise


def obter_rotas_disponiveis(url: str) -> List[str]:
    driver = None
    try:
        if not validar_url(url):
            return []
        
        driver = criar_driver()
        wait = WebDriverWait(driver, TIMEOUT_PADRAO)
        rotas_encontradas = []
        
        meus_bairros_limpos = [remover_acentos(b) for b in MEUS_BAIRROS]
        
        logger.info("[INFO] Iniciando mapeamento de rotas disponiveis...")
        driver.get(url)
        time.sleep(2)
        
        dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
        safe_click(driver, dropdown)
        time.sleep(1)
        
        opcoes = driver.find_elements(By.XPATH, "//div[@role='option']")
        
        for opt in opcoes:
            texto_original = opt.get_attribute("data-value") or opt.text
            if texto_original and texto_original != "Escolher":
                texto_limpo = remover_acentos(texto_original)
                if any(b_limpo in texto_limpo for b_limpo in meus_bairros_limpos):
                    rotas_encontradas.append(texto_original)
                    logger.info(f"[OK] Rota identificada: {texto_original}")
        
        driver.find_element(By.TAG_NAME, "body").click()
        time.sleep(0.5)
        
        logger.info(f"[RESUMO] Total de rotas compativeis: {len(rotas_encontradas)}")
        return rotas_encontradas
    
    except Exception as e:
        logger.error(f"[ERRO] Erro no mapeamento de rotas: {e}")
        return []
    
    finally:
        if driver:
            driver.quit()
            logger.debug("Driver encerrado (mapeamento)")


def enviar_formulario(url: str, rota: str, tentativa: int = 1) -> bool:
    driver = None
    try:
        driver = criar_driver()
        wait = WebDriverWait(driver, TIMEOUT_ENVIO)
        
        logger.info(f"[PROCESSANDO] Tentativa {tentativa}/{MAX_TENTATIVAS} - Rota: {rota}")
        driver.get(url)
        time.sleep(2)
        
        # 1. Preencher NOME COMPLETO
        preencher_input_por_pergunta(driver, wait, "NOME COMPLETO", NOME)
        
        # 2. Preencher ID
        preencher_input_por_pergunta(driver, wait, "ID", ID_FUNC)
        
        # 3. Selecionar rota no dropdown
        dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
        safe_click(driver, dropdown)
        time.sleep(1)
        
        opcao_xpath = f"//div[@role='option']//span[text()='{rota}']"
        opcao = wait.until(EC.element_to_be_clickable((By.XPATH, opcao_xpath)))
        safe_click(driver, opcao)
        time.sleep(0.5)
        logger.debug(f"Rota selecionada: {rota}")
        
        # 4. Selecionar "15 MINUTOS" - radio button com role=checkbox e aria-label
        radio_xpath = '//div[@role="checkbox" and @aria-label="15 MINUTOS"]'
        radio = wait.until(EC.element_to_be_clickable((By.XPATH, radio_xpath)))
        safe_click(driver, radio)
        time.sleep(0.5)
        logger.debug("Tempo selecionado: 15 MINUTOS")
        
        # 5. Clicar em Enviar
        btn_enviar = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Enviar']")))
        safe_click(driver, btn_enviar)
        
        # Verificação de Sucesso
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'registrada') or contains(text(), 'agradecemos') or contains(text(), 'enviado') or contains(text(), 'resposta')]")))
        logger.info(f"[OK] SUCESSO CONFIRMADO: {rota}")
        return True
        
    except Exception as e:
        logger.error(f"[ERRO] Falha no envio ({rota}): {e}")
        
        if tentativa < MAX_TENTATIVAS:
            logger.info(f"[RETRY] Aguardando {INTERVALO_RETRY}s antes de retry...")
            time.sleep(INTERVALO_RETRY)
            return enviar_formulario(url, rota, tentativa + 1)
        
        return False
    
    finally:
        if driver:
            driver.quit()
            logger.debug("Driver encerrado (envio)")


# ==================== MAIN ====================

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("INICIANDO AUTOMACAO DE FORMULARIOS - NOVO MODELO")
    logger.info("="*60)
    
    url_dia = input("Cole a URL do Forms: ").strip()
    
    if not validar_url(url_dia):
        logger.error("[ERRO] URL invalida. Encerrando...")
        exit(1)
    
    logger.info(f"URL validada: {url_dia[:50]}...")
    
    lista_de_rotas = obter_rotas_disponiveis(url_dia)
    
    if lista_de_rotas:
        lista_de_rotas = ordenar_rotas_por_preferencia(lista_de_rotas)
    
    if lista_de_rotas:
        logger.info(f"\n{'='*60}")
        logger.info(f"INICIANDO {len(lista_de_rotas)} ENVIOS")
        logger.info(f"{'='*60}\n")
        
        sucesso_count = 0
        falha_count = 0
        
        for idx, rota in enumerate(lista_de_rotas, 1):
            logger.info(f"\n[{idx}/{len(lista_de_rotas)}] Processando: {rota}")
            
            if enviar_formulario(url_dia, rota):
                sucesso_count += 1
            else:
                falha_count += 1
            
            if idx < len(lista_de_rotas):
                logger.info(f"[AGUARDANDO] {INTERVALO_ENTRE_ENVIOS}s ate proximo envio...")
                time.sleep(INTERVALO_ENTRE_ENVIOS)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RESUMO FINAL")
        logger.info(f"{'='*60}")
        logger.info(f"[OK] Sucessos: {sucesso_count}")
        logger.info(f"[ERRO] Falhas: {falha_count}")
        logger.info(f"Taxa de sucesso: {(sucesso_count/len(lista_de_rotas)*100):.1f}%")
        logger.info(f"{'='*60}\n")
    
    else:
        logger.error("[ERRO] Nenhuma rota compativel encontrada.")
        exit(1)