#!/usr/bin/env python
import os
import sys
import subprocess
import time
from pathlib import Path

def kill_running_instances():
    exe_name = "Z7_OfficeLetters.exe"
    print(f"[*] Verificando instâncias em execução de {exe_name}...")
    try:
        # Executa taskkill para forçar o fechamento do executável se estiver rodando
        result = subprocess.run(
            ["taskkill", "/F", "/IM", exe_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            print(f"[+] Instância ativa de {exe_name} foi finalizada.")
            # Aguarda um curto período para o Windows liberar o lock do arquivo
            time.sleep(1.0)
        else:
            if "não encontrado" in result.stderr.lower() or "not found" in result.stderr.lower():
                print(f"[+] Nenhuma instância de {exe_name} em execução.")
            else:
                print(f"[*] Aviso do taskkill: {result.stderr.strip()}")
    except Exception as e:
        print(f"[-] Erro ao tentar finalizar processos: {e}")

def check_file_lock(exe_path: Path) -> bool:
    if not exe_path.exists():
        return True
    try:
        # Tenta abrir o arquivo para escrita para ver se está travado
        with open(exe_path, "r+b") as f:
            pass
        return True
    except PermissionError:
        return False
    except Exception as e:
        print(f"[-] Erro ao testar trava do arquivo: {e}")
        return False

def main():
    project_dir = Path(__file__).resolve().parent
    exe_path = project_dir / "dist" / "Z7_OfficeLetters.exe"
    spec_path = project_dir / "auto_oficios.spec"

    print("=" * 60)
    print(" Iniciando Script de Compilação Segura (Z7 OfficeLetters)")
    print("=" * 60)

    # 1. Finalizar instâncias ativas
    kill_running_instances()

    # 2. Verificar se o arquivo de destino ainda está travado (com retentativas)
    if exe_path.exists():
        print("[*] Verificando acesso de escrita no arquivo executável...")
        locked = True
        for attempt in range(1, 11):
            if check_file_lock(exe_path):
                locked = False
                break
            print(f"[*] Tentativa {attempt}/10: Arquivo ainda travado, aguardando liberação do processo...")
            time.sleep(1.0)
            
        if locked:
            print(f"\n[ERRO CRÍTICO] O arquivo '{exe_path}' continua travado por outro processo após 10 segundos.")
            print("Por favor, feche o aplicativo ou qualquer outra ferramenta que o esteja utilizando e tente novamente.\n")
            sys.exit(1)
        print("[+] Arquivo de destino está livre para escrita.")

    # 3. Regenerar egg-info para garantir que a versão embarcada no exe esteja atualizada
    #    IMPORTANTE: Usar install NÃO-editável (-e) para que o PKG-INFO dentro
    #    de src/z7_officeletters.egg-info seja atualizado com a versão correta.
    print("[*] Regenerando egg-info a partir de pyproject.toml...")
    egg_info_dir = project_dir / "src" / "z7_officeletters.egg-info"
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", ".", "--no-deps", "--no-build-isolation"],
            cwd=str(project_dir),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("[+] Egg-info atualizado com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"[AVISO] Falha ao regenerar egg-info: {e.stderr.decode(errors='replace').strip()}")
        print("[*] A versão embarcada pode estar desatualizada. Continuando com egg-info existente...")

    # 4. Executar o PyInstaller
    if not spec_path.exists():
        print(f"[ERRO CRÍTICO] Arquivo de especificação '{spec_path}' não foi encontrado.")
        sys.exit(1)

    print(f"[*] Executando PyInstaller com {spec_path.name}...")
    cmd = [sys.executable, "-m", "PyInstaller", str(spec_path), "--noconfirm"]
    
    try:
        # Executa em tempo real mostrando a saída no console
        result = subprocess.run(cmd, check=True)
        print("\n" + "=" * 60)
        print("[SUCESSO] Compilação concluída com êxito!")
        print(f"O executável está disponível em: {exe_path}")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 60)
        print(f"[ERRO] O PyInstaller falhou com código de saída {e.returncode}.")
        print("=" * 60)
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
