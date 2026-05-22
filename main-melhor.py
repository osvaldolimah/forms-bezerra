import logging
import os
import time
import unicodedata
from typing import List, Optional
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

# Silenciar logging verbose do webdriver_manager
logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# ==================== CARREGAMENTO DE VARIÁVEIS DE AMBIENTE ====================
load_dotenv()

NOME = os.getenv("NOME_FUNCIONARIO", "").strip()
ID_FUNC = os.getenv("ID_FUNCIONARIO", "").strip()
TELEFONE = os.getenv("TELEFONE", "").strip()

# Validação de dados carregados
if not all([NOME, ID_FUNC, TELEFONE]):
    logger.error("[ERRO] Variaveis de ambiente nao configuradas. Crie um arquivo .env com NOME_FUNCIONARIO, ID_FUNCIONARIO e TELEFONE")
    exit(1)

# ==================== DADOS ====================
MEUS_BAIRROS = [
    "Cambeba", "Guararapes", "Benfica", "Itaperi", "Rodolfo Teófilo", "Cajazeiras",
    "Aerolândia", "Alto da Balança", "Boa Vista", "Luciano Cavalcante",
    "Dias Macedo", "Damas", "Montese", "Jardim América", "Parreão",
    "Fátima", "Serrinha", "Itaperi", "Cidade dos Funcionários",
    "Parque Iracema", "Parque Manibura", "Parquelandia", "Amadeu Furtado",
    "Rodolfo Teofilo", "São Gerardo", "Bom Futuro", "Vila União"
]

# ==================== BAIRROS PREFERIDOS ====================
# Define a ordem de prioridade para envio dos formularios
# Se um bairro preferido nao estiver disponivel, eh ignorado
# Os bairros nao listados aqui serao processados por ultimo
BAIRROS_PREFERIDOS = [
    "Parque Iracema",
    "Cajazeiras",
    "Cambeba",
    "Damas",
    "Itaperi",
    "Guararapes",
    "Luciano Cavalcante"
]

# Configurações
TIMEOUT_PADRAO = 15
TIMEOUT_ENVIO = 20
INTERVALO_ENTRE_ENVIOS = 3
MAX_TENTATIVAS = 2
INTERVALO_RETRY = 2

# ==================== FUNÇÕES AUXILIARES ====================

def ordenar_rotas_por_preferencia(rotas: List[str]) -> List[str]:
    """
    Reordena as rotas encontradas de acordo com a preferencia definida em BAIRROS_PREFERIDOS.
    Bairros nao listados em BAIRROS_PREFERIDOS sao colocados no final.
    
    Args:
        rotas: Lista de rotas encontradas
        
    Returns:
        Lista de rotas reordenada por preferencia
    """
    rotas_preferidas = []
    rotas_restantes = []
    
    # Normalizar os bairros preferidos para comparacao
    bairros_pref_normalizados = {remover_acentos(b): b for b in BAIRROS_PREFERIDOS}
    
    # Separar rotas: preferidas vs restantes
    for rota in rotas:
        rota_normalizada = remover_acentos(rota)
        # Verificar se algum bairro preferido esta na rota
        encontrou_preferido = False
        for bairro_pref_norm, bairro_pref_original in bairros_pref_normalizados.items():
            if bairro_pref_norm in rota_normalizada:
                rotas_preferidas.append((BAIRROS_PREFERIDOS.index(bairro_pref_original), rota))
                encontrou_preferido = True
                break
        
        if not encontrou_preferido:
            rotas_restantes.append(rota)
    
    # Ordenar rotas preferidas pela ordem em BAIRROS_PREFERIDOS
    rotas_preferidas.sort(key=lambda x: x[0])
    resultado = [rota for _, rota in rotas_preferidas] + rotas_restantes
    
    return resultado


def remover_acentos(texto: str) -> str:
    """
    Normaliza o texto removendo acentos e convertendo para minúsculas.
    
    Args:
        texto: String a normalizar
        
    Returns:
        String normalizada sem acentos e em minúsculas
    """
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()


def validar_url(url: str) -> bool:
    """
    Valida se a URL é um formulário Google válido.
    
    Args:
        url: URL a validar
        
    Returns:
        True se é URL válida, False caso contrário
    """
    try:
        result = urlparse(url)
        if not result.scheme or not result.netloc:
            logger.error(f"URL inválida: {url}")
            return False
        
        # Aceita URLs completas (docs.google.com/forms) e encurtadas (forms.gle)
        if "docs.google.com/forms" not in url and "forms.gle" not in url:
            logger.warning(f"URL nao parece ser um formulario Google: {url}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Erro ao validar URL: {e}")
        return False


def safe_click(driver: webdriver.Chrome, element) -> None:
    """
    Garante o clique via JavaScript para evitar intercepções.
    
    Args:
        driver: WebDriver do Selenium
        element: Elemento a clicar
    """
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


def preencher_input(driver: webdriver.Chrome, wait: WebDriverWait, index: int, texto: str) -> None:
    """
    Localiza o input pelo índice e realiza o preenchimento seguro.
    
    Args:
        driver: WebDriver do Selenium
        wait: WebDriverWait para esperas explícitas
        index: Índice do input
        texto: Texto a inserir
    """
    xpath_inputs = "//input[@type='text' or @type='number']"

    wait.until(
        lambda d: len([el for el in d.find_elements(By.XPATH, xpath_inputs) if el.is_displayed()]) > index
    )
    inputs = [el for el in driver.find_elements(By.XPATH, xpath_inputs) if el.is_displayed()]

    if len(inputs) <= index:
        raise IndexError(
            f"Não foi possível localizar o input de índice {index}. "
            f"Encontrados {len(inputs)} inputs visíveis."
        )

    campo = inputs[index]
    safe_click(driver, campo)
    campo.clear()
    campo.send_keys(texto)


def obter_elemento_botao(driver: webdriver.Chrome, wait: WebDriverWait, texto_botao: str):
    """
    Localiza botão por texto - padrão do main.py original.
    
    Args:
        driver: WebDriver do Selenium
        wait: WebDriverWait para esperas explícitas
        texto_botao: Texto do botão a procurar
        
    Returns:
        Elemento do botão ou None se não encontrado
    """
    try:
        xpath = f"//span[normalize-space(text())='{texto_botao}' or normalize-space(text())='Próxima']" if texto_botao == "Avançar" else f"//span[normalize-space(text())='{texto_botao}']"
        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)), timeout=5)
        logger.debug(f"Botao '{texto_botao}' encontrado")
        return elemento
    except Exception as e:
        logger.debug(f"Botao '{texto_botao}' nao encontrado: {e}")
        return None


def criar_driver() -> webdriver.Chrome:
    """
    Cria uma nova instância do Chrome WebDriver.
    
    Returns:
        WebDriver configurado
    """
    try:
        options = webdriver.ChromeOptions()
        # Descomente a linha abaixo para modo headless (sem interface visual)
        # options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Suprimir erros internos do Chrome (GCM, logging, etc)
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--log-level=3")  # Apenas erros críticos
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
    """
    Mapeia as rotas no formulário que coincidem com a lista de bairros.
    
    Args:
        url: URL do formulário Google
        
    Returns:
        Lista de rotas encontradas
    """
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
        
        # Página 1: Identificação
        preencher_input(driver, wait, 0, NOME)
        preencher_input(driver, wait, 1, ID_FUNC)
        
        btn_avancar = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima']")))
        safe_click(driver, btn_avancar)

        # Página 2: Mapeamento do Dropdown
        time.sleep(2)
        dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
        safe_click(driver, dropdown)
        
        time.sleep(2)
        opcoes = driver.find_elements(By.XPATH, "//div[@role='option']")
        
        for opt in opcoes:
            texto_original = opt.get_attribute("data-value") or opt.text
            if texto_original and texto_original != "Escolher":
                texto_limpo = remover_acentos(texto_original)
                if any(b_limpo in texto_limpo for b_limpo in meus_bairros_limpos):
                    rotas_encontradas.append(texto_original)
                    logger.info(f"[OK] Rota identificada: {texto_original}")
        
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
    """
    Preenche e envia o formulario para uma rota especifica, aguardando confirmacao.
    
    Args:
        url: URL do formulario Google
        rota: Nome da rota a selecionar
        tentativa: Numero da tentativa atual
        
    Returns:
        True se sucesso, False se falha
    """
    driver = None
    try:
        driver = criar_driver()
        wait = WebDriverWait(driver, TIMEOUT_ENVIO)
        
        logger.info(f"[PROCESSANDO] Tentativa {tentativa}/{MAX_TENTATIVAS} - Rota: {rota}")
        driver.get(url)
        
        # Pagina 1: Identificacao
        preencher_input(driver, wait, 0, NOME)
        preencher_input(driver, wait, 1, ID_FUNC)
        
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima']")))
        safe_click(driver, btn)

        # Pagina 2: Selecao da Rota
        time.sleep(2)
        dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
        safe_click(driver, dropdown)
        time.sleep(1)
        
        opcao_xpath = f"//div[@role='option']//span[text()='{rota}']"
        opcao = wait.until(EC.element_to_be_clickable((By.XPATH, opcao_xpath)))
        safe_click(driver, opcao)
        
        time.sleep(1)
        btn2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima']")))
        safe_click(driver, btn2)

        # Pagina 3: Telefone
        time.sleep(2)
        preencher_input(driver, wait, 0, TELEFONE)
        
        btn_enviar = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Enviar']")))
        safe_click(driver, btn_enviar)

        # Verificacao de Sucesso (Aguarda o Google processar o envio)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'registrada') or contains(text(), 'agradecemos')]")))
        logger.info(f"[OK] SUCESSO CONFIRMADO: {rota}")
        return True
        
    except Exception as e:
        logger.error(f"[ERRO] Falha no envio ({rota}): {e}")
        
        # Retry para erros temporarios
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
    logger.info("INICIANDO AUTOMACAO DE FORMULARIOS")
    logger.info("="*60)
    
    url_dia = input("Cole a URL do Forms: ").strip()
    
    if not validar_url(url_dia):
        logger.error("[ERRO] URL invalida. Encerrando...")
        exit(1)
    
    logger.info(f"URL validada: {url_dia[:50]}...")
    
    lista_de_rotas = obter_rotas_disponiveis(url_dia)
    
    # Reordenar rotas de acordo com preferencia
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
            
            # Intervalo de segurança entre envios
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
