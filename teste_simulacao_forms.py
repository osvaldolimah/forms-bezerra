#!/usr/bin/env python3
"""Rotina de teste para simular o preenchimento de um Google Forms.

Use quando o formulário real estiver indisponível, mas você tiver o HTML salvo
ou uma URL equivalente com a mesma estrutura.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


DEFAULT_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfCSutIeJrY-AOm7jz3ImNq5hFEBl7SSJmnkVNV5mBNFXUgFA/viewform"
DEFAULT_NOME = "Tiago Bezerra"
DEFAULT_ID_FUNC = "2359946"
DEFAULT_TELEFONE = "85988299118"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simula o preenchimento de um Google Forms.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url", default=DEFAULT_URL, help="URL do formulário para testar.")
    source.add_argument("--html", help="Caminho para um arquivo HTML salvo do formulário.")
    parser.add_argument("--nome", default=DEFAULT_NOME, help="Valor a usar no campo nome.")
    parser.add_argument("--id-func", default=DEFAULT_ID_FUNC, help="Valor a usar no campo ID.")
    parser.add_argument("--telefone", default=DEFAULT_TELEFONE, help="Valor a usar no campo telefone.")
    parser.add_argument("--rota", help="Rota a selecionar na etapa de dropdown.")
    parser.add_argument("--headless", action="store_true", help="Executa sem abrir janela do navegador.")
    return parser.parse_args()


def xpath_literal(texto: str) -> str:
    if "'" not in texto:
        return f"'{texto}'"
    if '"' not in texto:
        return f'"{texto}"'
    partes = texto.split("'")
    return "concat(" + ", \"'\", ".join(f"'{parte}'" for parte in partes) + ")"


def criar_driver(headless: bool = True) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            options.binary_location = path
            break

    chromedriver_paths = [
        r"C:\chromedriver.exe",
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
    ]

    for path in chromedriver_paths:
        if os.path.exists(path):
            return webdriver.Chrome(service=Service(path), options=options)

    try:
        return webdriver.Chrome(options=options)
    except Exception:
        from webdriver_manager.chrome import ChromeDriverManager

        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def carregar_fonte(driver: webdriver.Chrome, url: Optional[str], html_path: Optional[str]) -> None:
    if html_path:
        caminho = Path(html_path).expanduser().resolve()
        if not caminho.exists():
            raise FileNotFoundError(f"HTML não encontrado: {caminho}")
        driver.get(caminho.as_uri())
        return
    if not url:
        raise ValueError("Informe --url ou --html.")
    driver.get(url)


def elementos_editaveis_visiveis(root) -> List:
    elementos = root.find_elements(
        By.XPATH,
        ".//textarea | .//input[(@type='text' or @type='number') and not(@type='hidden')]",
    )
    return [el for el in elementos if el.is_displayed()]


def preencher_elemento(driver: webdriver.Chrome, elemento, texto: str) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
    time.sleep(0.2)
    if elemento.tag_name.lower() == "textarea":
        try:
            elemento.clear()
        except Exception:
            pass
    else:
        driver.execute_script("arguments[0].focus();", elemento)
        driver.execute_script("arguments[0].value = '';", elemento)

    driver.execute_script("arguments[0].value = arguments[1];", elemento, texto)
    driver.execute_script(
        """
        var el = arguments[0];
        ['input', 'change', 'blur'].forEach(function(evtName) {
            el.dispatchEvent(new Event(evtName, { bubbles: true }));
        });
        """,
        elemento,
    )


def preencher_por_pergunta(driver, wait, pergunta: str, texto: str) -> None:
    bloco_xpath = (
        f"//div[@jsmodel='CP1oW'][.//*[self::span or self::div or self::label]"
        f"[contains(normalize-space(.), {xpath_literal(pergunta)})]]"
    )

    try:
        container = wait.until(EC.presence_of_element_located((By.XPATH, bloco_xpath)))
    except Exception:
        pergunta_xpath = (
            f"//*[self::span or self::div or self::label][contains(normalize-space(.), {xpath_literal(pergunta)})]"
        )
        pergunta_element = wait.until(EC.presence_of_element_located((By.XPATH, pergunta_xpath)))
        try:
            container = pergunta_element.find_element(By.XPATH, "./ancestor::div[@jsmodel='CP1oW'][1]")
        except Exception:
            container = pergunta_element

    elementos = elementos_editaveis_visiveis(container)
    if not elementos:
        elementos = elementos_editaveis_visiveis(driver)
    if not elementos:
        raise RuntimeError(f"Não foi possível localizar o campo da pergunta: {pergunta}")

    preencher_elemento(driver, elementos[0], texto)


def clicar_por_texto(driver, wait, textos: List[str]) -> None:
    xpath = " | ".join(
        f"//span[normalize-space(text())={xpath_literal(texto)}] | //div[@role='button' and normalize-space(.)={xpath_literal(texto)}]"
        for texto in textos
    )
    elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
    time.sleep(0.3)
    try:
        elemento.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elemento)


def selecionar_rota(driver, wait, rota: Optional[str]) -> Optional[str]:
    dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='listbox']")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
    time.sleep(0.2)
    try:
        dropdown.click()
    except Exception:
        driver.execute_script("arguments[0].click();", dropdown)

    time.sleep(1)
    opcoes = [opt for opt in driver.find_elements(By.XPATH, "//div[@role='option']") if (opt.text or "").strip() and (opt.text or "").strip() != "Escolher"]
    if not opcoes:
        raise RuntimeError("Nenhuma opção de rota encontrada no dropdown.")

    escolhida = None
    if rota:
        for opt in opcoes:
            texto = (opt.text or "").strip()
            if texto == rota:
                escolhida = opt
                break

    if escolhida is None:
        escolhida = opcoes[0]

    texto_escolhido = (escolhida.text or "").strip()
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", escolhida)
    time.sleep(0.2)
    try:
        escolhida.click()
    except Exception:
        driver.execute_script("arguments[0].click();", escolhida)

    return texto_escolhido


def simular(args: argparse.Namespace) -> int:
    driver = criar_driver(headless=args.headless)
    wait = WebDriverWait(driver, 25)
    passos = []

    try:
        carregar_fonte(driver, args.url, args.html)
        passos.append(f"Página carregada: {driver.title or 'sem título'}")

        preencher_por_pergunta(driver, wait, "Qual seu nome?", args.nome)
        passos.append("Nome preenchido")

        preencher_por_pergunta(driver, wait, "Qual seu ID?", args.id_func)
        passos.append("ID preenchido")

        clicar_por_texto(driver, wait, ["Avançar", "Próxima", "Next"])
        passos.append("Avançou da página 1")

        rota_escolhida = selecionar_rota(driver, wait, args.rota)
        passos.append(f"Rota selecionada: {rota_escolhida}")

        clicar_por_texto(driver, wait, ["Avançar", "Próxima", "Next"])
        passos.append("Avançou da página 2")

        time.sleep(1.5)
        campos = elementos_editaveis_visiveis(driver)
        if not campos:
            raise RuntimeError("Campo de telefone não encontrado na terceira página.")

        preencher_elemento(driver, campos[0], args.telefone)
        passos.append("Telefone preenchido")

        print("SIMULACAO OK")
        for passo in passos:
            print(f"- {passo}")
        print("- Modo: sem envio final")
        return 0
    except Exception as exc:
        print("SIMULACAO FALHOU")
        for passo in passos:
            print(f"- {passo}")
        print(f"- Erro: {type(exc).__name__}: {exc}")
        return 1
    finally:
        driver.quit()


def main() -> None:
    args = parse_args()
    raise SystemExit(simular(args))


if __name__ == "__main__":
    main()