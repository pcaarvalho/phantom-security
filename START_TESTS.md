# 🚀 PHANTOM Security AI - COMANDOS PARA TESTE

## ✅ Frontend está funcionando!
Build concluído com sucesso. Agora execute os testes:

## 🧪 TESTE 1 - Frontend Standalone

```bash
# Terminal 1 - Frontend
cd /Users/pedro/PHANTONSECURITY/phantom-security/frontend
npm run dev
```

**✅ Resultado esperado:**
- Servidor em http://localhost:3000
- Dashboard carrega com interface moderna
- Dados mock aparecem nos cards

---

## 🧪 TESTE 2 - Backend Simples

```bash
# Terminal 2 - Backend
cd /Users/pedro/PHANTONSECURITY/phantom-security/backend

# Ativar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Testar imports
python -c "
import sys
sys.path.append('.')
from app.main import app
print('✅ Backend OK!')
"

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

**✅ Resultado esperado:**
- API em http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## 🧪 TESTE 3 - Scanner Básico

```bash
# No terminal backend
python -c "
import asyncio
import sys
sys.path.append('.')

from app.core.scanner.vulnerability_scanner import VulnerabilityScanner

async def test():
    scanner = VulnerabilityScanner('scanme.nmap.org')
    if scanner.validate_target():
        print('✅ Scanner validation OK')
    else:
        print('❌ Validation failed')

asyncio.run(test())
print('🎉 Scanner test complete!')
"
```

---

## 🧪 TESTE 4 - AI Fallback

```bash
# Teste análise AI
python -c "
import sys
sys.path.append('.')

from app.core.ai.analyzer import AIThreatAnalyzer

analyzer = AIThreatAnalyzer()
mock_data = {
    'target': 'test.com',
    'nuclei_scan': {'vulnerabilities': [{'severity': 'high'}]},
    'port_scan': {'ports': []}
}

result = analyzer._fallback_analysis(mock_data)
print(f'✅ Risk Score: {result[\"risk_score\"]}')
print(f'✅ Summary: {result[\"executive_summary\"][:50]}...')
"
```

---

## 🐳 TESTE 5 - Docker Completo

```bash
# Na raiz do projeto
cd /Users/pedro/PHANTONSECURITY/phantom-security

# Iniciar todos os serviços
docker compose up -d

# Ver status
docker compose ps

# Ver logs
docker compose logs -f
```

**Acessos:**
- Frontend: http://localhost:3000
- Backend: http://localhost:8000/docs  
- Health: http://localhost:8000/health

---

## 🎯 TESTE DE FUNCIONALIDADE

1. Abrir http://localhost:3000
2. Ver dashboard com dados mock
3. Inserir target: "scanme.nmap.org" 
4. Clicar "Start Scan"
5. Ver animação de progresso
6. Verificar se dados aparecem

---

## ✅ CHECKLIST DE SUCESSO

- [ ] Frontend carrega sem erros
- [ ] Dashboard mostra interface bonita
- [ ] Backend responde em /docs
- [ ] Health check funciona (/health)
- [ ] Scanner validation OK
- [ ] AI fallback retorna dados
- [ ] Docker services sobem sem erro

**Se todos passarem = PHANTOM está funcionando! 🛡️**

---

## 📞 Se algo falhar:

```bash
# Limpar tudo e recomeçar
docker compose down
docker system prune -f

# Frontend
cd frontend && rm -rf node_modules && npm install

# Backend  
cd backend && pip install -r requirements.txt

# Tentar novamente
docker compose up -d
```