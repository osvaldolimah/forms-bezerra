from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import unicodedata

# --- DADOS ---
NOME = "Osvaldo Holanda"
ID_FUNC = "2445201"
TELEFONE = "85988449973"

# Lista atualizada de bairros
MEUS_BAIRROS = [
    "Cambeba", "Guararapes", "Benfica", "Itaperi", "Rodolfo Teófilo", "Cajazeiras", 
    "Aerolândia", "Alto da Balança", "Boa Vista", "Luciano Cavalcante", 
    "Dias Macedo", "Damas", "Montese", "Jardim América", "Parreão", 
    "Fátima", "Serrinha", "Itaperi", "Cidade dos Funcionários", 
    "Parque Iracema", "Parque Manibura", "Parquelandia", "Amadeu Furtado", 
    "Rodolfo Teofilo", "São Gerardo", "Bom Futuro", "Vila União"
]

def remover_acentos(texto):
    """Normaliza o texto removendo acentos e convertendo para minúsculas."""
    if not texto:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def safe_click(driver, element):
    """Garante o clique via JavaScript para evitar intercepções."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    try:
        element.click()
    except:
        driver.execute_script("arguments[0].click();", element)

def preencher_input(driver, wait, index, texto):
    """Localiza o input pelo índice e realiza o preenchimento seguro."""
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

def obter_rotas_disponiveis(url):
    """Mapeia as rotas no formulário que coincidem com a lista de bairros."""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 15)
    rotas_encontradas = []
    
    meus_bairros_limpos = [remover_acentos(b) for b in MEUS_BAIRROS]
    
    try:
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
                    print(f"✅ Rota identificada: {texto_original}")
    
    except Exception as e:
        print(f"❌ Erro no mapeamento: {e}")
    finally:
        driver.quit()
    return rotas_encontradas

def enviar_formulario(url, rota):
    """Preenche e envia o formulário para uma rota específica, aguardando confirmação."""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 20)
    
    try:
        driver.get(url)
        # Página 1
        preencher_input(driver, wait, 0, NOME)
        preencher_input(driver, wait, 1, ID_FUNC)
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Avançar' or normalize-space(text())='Próxima']")))
        safe_click(driver, btn)

        # Página 2: Seleção da Rota
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

        # Página 3: Telefone
        time.sleep(2)
        preencher_input(driver, wait, 0, TELEFONE)
        
        btn_enviar = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[normalize-space(text())='Enviar']")))
        safe_click(driver, btn_enviar)

        # Verificação de Sucesso (Aguarda o Google processar o envio)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'registrada') or contains(text(), 'agradecemos')]")))
        print(f">>> SUCESSO CONFIRMADO: {rota}")
        
    except Exception as e:
        print(f"❌ Falha no envio ({rota}): {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    url_dia = input("Cole a URL do Forms: ")
    lista_de_rotas = obter_rotas_disponiveis(url_dia)
    
    if lista_de_rotas:
        print(f"\nIniciando {len(lista_de_rotas)} envios...")
        for r in lista_de_rotas:
            enviar_formulario(url_dia, r)
            # Intervalo de segurança para evitar bloqueios de spam e garantir gravação na planilha
            time.sleep(3)
    else:
        print("Nenhuma rota compatível encontrada.")