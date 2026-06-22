import sys
import zipfile
from pathlib import Path

def main():
    project_dir = Path(__file__).resolve().parent.parent
    
    # Import version dynamically
    sys.path.insert(0, str(project_dir / "src"))
    from z7_officeletters import APP_VERSION
    
    zip_path = project_dir / "dist" / f"Z7_OfficeLetters_v{APP_VERSION}.zip"
    
    print(f"[*] Criando arquivo ZIP em {zip_path}...")
    
    files_to_zip = [
        (project_dir / "dist" / "Z7_OfficeLetters.exe", "Z7_OfficeLetters.exe"),
        (project_dir / "config.json", "config.json"),
        (project_dir / "templates" / "modelo_envelope.docx", "templates/modelo_envelope.docx"),
        (project_dir / "templates" / "modelo_mocao.docx", "templates/modelo_mocao.docx"),
        (project_dir / "templates" / "modelo_planilha.xlsx", "templates/modelo_planilha.xlsx"),
        (project_dir / "templates" / "modelo_requer_pesar.docx", "templates/modelo_requer_pesar.docx"),
        (project_dir / "ender" / "enderecamentos_padrao.docx", "ender/enderecamentos_padrao.docx"),
    ]
    
    # Certificar que o arquivo ZIP anterior seja excluído antes de criar o novo
    if zip_path.exists():
        zip_path.unlink()
        print("[*] Arquivo ZIP anterior removido.")
        
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in files_to_zip:
            if not src.exists():
                raise FileNotFoundError(f"Arquivo necessário não encontrado: {src}")
            zf.write(src, arcname)
            print(f"[+] Adicionado: {arcname} ({src.stat().st_size} bytes)")
            
    print(f"[SUCESSO] ZIP de release gerado com sucesso!")

if __name__ == "__main__":
    main()
