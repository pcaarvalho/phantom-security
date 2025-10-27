#!/usr/bin/env python3
"""
Teste básico do PHANTOM Security AI
Execute este script para verificar se os componentes principais funcionam
"""

import sys
import requests
import time
import json

def test_imports():
    """Testa se os imports principais funcionam"""
    print("🧪 Testando imports...")
    
    try:
        from app.main import app
        print("✅ FastAPI app importada com sucesso")
    except Exception as e:
        print(f"❌ Erro ao importar app: {e}")
        return False
    
    try:
        from app.core.scanner.vulnerability_scanner import VulnerabilityScanner
        print("✅ Scanner importado com sucesso")
    except Exception as e:
        print(f"❌ Erro ao importar scanner: {e}")
        return False
    
    try:
        from app.core.ai.analyzer import AIThreatAnalyzer
        print("✅ AI Analyzer importado com sucesso")
    except Exception as e:
        print(f"❌ Erro ao importar AI analyzer: {e}")
        return False
    
    return True

def test_scanner_basic():
    """Testa scanner básico sem dependências externas"""
    print("\n🔍 Testando scanner básico...")
    
    try:
        from app.core.scanner.base_scanner import BaseScanner
        
        class TestScanner(BaseScanner):
            async def scan(self):
                return {"test": "ok", "target": self.target}
        
        scanner = TestScanner("example.com")
        if scanner.validate_target():
            print("✅ Validação de target funcionando")
        else:
            print("❌ Validação de target falhou")
            return False
            
        print("✅ Scanner básico OK")
        return True
        
    except Exception as e:
        print(f"❌ Erro no scanner básico: {e}")
        return False

def test_ai_fallback():
    """Testa análise AI com fallback (sem API key)"""
    print("\n🤖 Testando AI fallback...")
    
    try:
        from app.core.ai.analyzer import AIThreatAnalyzer
        
        analyzer = AIThreatAnalyzer()
        
        # Dados mock para teste
        mock_scan_data = {
            "target": "test.example.com",
            "nuclei_scan": {
                "vulnerabilities": [
                    {"severity": "high", "template_name": "Test Vuln"}
                ]
            },
            "port_scan": {
                "ports": [{"port": 80, "service": "http"}]
            }
        }
        
        # Usar análise fallback (sem OpenAI)
        result = analyzer._fallback_analysis(mock_scan_data)
        
        if "risk_score" in result and "executive_summary" in result:
            print("✅ AI fallback funcionando")
            print(f"   Risk Score: {result['risk_score']}")
            return True
        else:
            print("❌ AI fallback não retornou dados esperados")
            return False
            
    except Exception as e:
        print(f"❌ Erro no AI fallback: {e}")
        return False

def test_api_health():
    """Testa se a API está respondendo (se estiver rodando)"""
    print("\n🌐 Testando API health...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API respondendo corretamente")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ API retornou status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("⚠️  API não está rodando (isso é normal se não iniciou ainda)")
        return None
    except Exception as e:
        print(f"❌ Erro ao testar API: {e}")
        return False

def test_frontend_build():
    """Testa se o frontend pode ser buildado"""
    print("\n⚛️  Testando frontend...")
    
    import os
    import subprocess
    
    frontend_dir = "/Users/pedro/PHANTONSECURITY/phantom-security/frontend"
    
    if not os.path.exists(os.path.join(frontend_dir, "package.json")):
        print("❌ Frontend não encontrado")
        return False
    
    try:
        # Verificar se node_modules existe
        if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
            print("⚠️  node_modules não encontrado - execute 'npm install' primeiro")
            return None
        
        # Testar build simples
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ Frontend build OK")
            return True
        else:
            print(f"❌ Frontend build falhou: {result.stderr[:200]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️  Build timeout - pode precisar de mais tempo")
        return None
    except Exception as e:
        print(f"❌ Erro ao testar frontend: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("🚀 PHANTOM Security AI - Teste Inicial\n")
    
    # Mudar para diretório backend
    import os
    backend_dir = "/Users/pedro/PHANTONSECURITY/phantom-security/backend"
    if os.path.exists(backend_dir):
        os.chdir(backend_dir)
        sys.path.append(backend_dir)
    
    tests = [
        ("Imports", test_imports),
        ("Scanner Básico", test_scanner_basic),
        ("AI Fallback", test_ai_fallback),
        ("API Health", test_api_health),
        ("Frontend Build", test_frontend_build),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ Erro inesperado em {test_name}: {e}")
            results[test_name] = False
    
    # Resumo
    print("\n" + "="*50)
    print("📊 RESUMO DOS TESTES")
    print("="*50)
    
    passed = 0
    total = 0
    
    for test_name, result in results.items():
        total += 1
        if result is True:
            print(f"✅ {test_name}: PASSOU")
            passed += 1
        elif result is False:
            print(f"❌ {test_name}: FALHOU")
        else:
            print(f"⚠️  {test_name}: PULADO/PENDENTE")
    
    print(f"\n🎯 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! Sistema está funcionando.")
    elif passed > total // 2:
        print("✨ Maioria dos testes passou. Sistema parece funcional.")
    else:
        print("⚠️  Muitos testes falharam. Verifique dependências.")
    
    print("\n📋 PRÓXIMOS PASSOS:")
    if results["API Health"] is None:
        print("1. Inicie a API: cd backend && uvicorn app.main:app --reload")
    if results["Frontend Build"] is None:
        print("2. Instale dependências frontend: cd frontend && npm install")
    print("3. Use Docker para ambiente completo: docker compose up -d")

if __name__ == "__main__":
    main()