# 🧪 TESTE INICIAL - PHANTOM Security AI

## ⚡ Teste Rápido (5 minutos)

### 1️⃣ **Teste Frontend Standalone**

```bash
# Navegar para frontend
cd frontend

# Instalar dependências (primeira vez)
npm install

# Iniciar servidor de desenvolvimento
npm run dev
```

**✅ Resultado esperado:**
- Server rodando em http://localhost:3000
- Dashboard carrega com interface moderna
- Botões e formulários funcionam
- Mock data aparece nos cards

---

### 2️⃣ **Teste Backend Simples (Sem Banco)**

```bash
# Em outro terminal, navegar para backend
cd backend

# Criar ambiente virtual Python
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependências (primeira vez)
pip install -r requirements.txt

# Testar servidor simples
python -c "
import sys
sys.path.append('.')
from app.main import app
from app.core.ai.analyzer import AIThreatAnalyzer

print('✅ FastAPI app OK')
analyzer = AIThreatAnalyzer()
print('✅ AI Analyzer OK')
print('🎉 Backend components working!')
"

# Iniciar servidor de desenvolvimento (sem banco)
uvicorn app.main:app --reload --port 8000
```

**✅ Resultado esperado:**
- Server rodando em http://localhost:8000
- API docs em http://localhost:8000/docs
- Health check funciona: http://localhost:8000/health

---

### 3️⃣ **Teste de Scanner Básico**

```bash
# No terminal backend, teste o scanner
python -c "
import asyncio
import sys
sys.path.append('.')

from app.core.scanner.base_scanner import BaseScanner

class TestScanner(BaseScanner):
    async def scan(self):
        return {'status': 'success', 'target': self.target}

async def test():
    scanner = TestScanner('example.com')
    print('✅ Target validation:', scanner.validate_target())
    result = await scanner.scan()
    print('✅ Scanner result:', result)

asyncio.run(test())
"
```

**✅ Resultado esperado:**
```
✅ Target validation: True
✅ Scanner result: {'status': 'success', 'target': 'example.com'}
```

---

### 4️⃣ **Teste de AI Fallback**

```bash
# Teste análise AI sem OpenAI key
python -c "
import sys
sys.path.append('.')

from app.core.ai.analyzer import AIThreatAnalyzer

analyzer = AIThreatAnalyzer()

mock_data = {
    'target': 'test.com',
    'nuclei_scan': {
        'vulnerabilities': [
            {'severity': 'high', 'template_name': 'Test Vuln 1'},
            {'severity': 'medium', 'template_name': 'Test Vuln 2'}
        ]
    },
    'port_scan': {'ports': [{'port': 80, 'service': 'http'}]}
}

result = analyzer._fallback_analysis(mock_data)
print('✅ Risk Score:', result['risk_score'])
print('✅ Executive Summary:', result['executive_summary'][:100] + '...')
print('✅ AI Fallback working!')
"
```

**✅ Resultado esperado:**
```
✅ Risk Score: 65
✅ Executive Summary: Automated security scan of test.com completed...
✅ AI Fallback working!
```

---

## 🐳 Teste Completo com Docker

### Para ambiente completo (recomendado para demonstrações):

```bash
# Na raiz do projeto
cd /Users/pedro/PHANTONSECURITY/phantom-security

# Iniciar todos os serviços
docker compose up -d

# Verificar status
docker compose ps

# Logs em tempo real
docker compose logs -f
```

**✅ Resultado esperado:**
- 5 serviços rodando: postgres, redis, backend, frontend, celery_worker
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 🎯 Teste de Funcionalidade Completa

### Com todos os serviços rodando:

1. **Abrir Dashboard**: http://localhost:3000
2. **Inserir target**: `scanme.nmap.org` (target legal para testes)
3. **Iniciar scan**: Clicar em "Start Scan"
4. **Aguardar**: Progress bar deve aparecer
5. **Ver resultados**: Cards devem atualizar com dados do scan

---

## ❌ Problemas Comuns

### Frontend não carrega:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Backend não inicia:
```bash
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

### Docker problemas:
```bash
docker compose down
docker system prune -f
docker compose up -d --build
```

### Porta ocupada:
```bash
# Parar serviços na porta
lsof -ti:3000 | xargs kill -9  # Frontend
lsof -ti:8000 | xargs kill -9  # Backend
```

---

## 🎉 Sucesso!

**Se você conseguir:**
- ✅ Frontend carrega em localhost:3000
- ✅ Backend responde em localhost:8000/docs
- ✅ Scanner básico funciona
- ✅ AI fallback retorna análise

**Então o PHANTOM Security AI está funcionando! 🛡️**

---

## 📱 Demonstração para Clientes

Para impressionar clientes, use:
1. **Target público**: `scanme.nmap.org` ou `testphp.vulnweb.com`
2. **Mostre progress em tempo real**
3. **Destaque risk score e vulnerabilities**
4. **Gere relatório PDF**

**⚠️ IMPORTANTE:** Só escaneie targets que você tem permissão!