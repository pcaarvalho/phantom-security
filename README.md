# PHANTOM Security

Comprehensive vulnerability detection and security analysis platform. PHANTOM combines industry-standard security tools with advanced analysis to discover and evaluate vulnerabilities in web applications and network infrastructure.

## Overview

PHANTOM Security is a comprehensive vulnerability detection platform that:

- **Discovers vulnerabilities** using industry-standard tools (Nmap, Nuclei, custom scanners)
- **Analyzes findings** with advanced analysis for contextualized insights
- **Generates reports** with executive summaries and technical details
- **Operates continuously** supporting 24/7 scanning operations

## 🏗️ Architecture

### Frontend
- **Next.js 14** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** + **Shadcn/ui** for modern UI
- **Recharts** for data visualization

### Backend
- **FastAPI** (Python 3.11+) for high-performance API
- **Celery** + **Redis** for async task processing
- **PostgreSQL** for data persistence
- **Advanced analysis** services for vulnerability assessment

### Security Tools
- **Nmap** for port scanning
- **Nuclei** for vulnerability detection
- **Custom scanners** for web application testing

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Required API keys for external services (if using external analysis)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/phantom-security.git
cd phantom-security
```

### 2. Environment Setup

```bash
# Backend configuration
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# Frontend configuration  
cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local with your settings
```

### 3. Start with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Access Application

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Celery Monitor**: http://localhost:5555 (optional)

## Development Setup

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --port 8000

# Start Celery worker (in another terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Usage

### Starting a Security Scan

1. **Access Dashboard**: Navigate to http://localhost:3000/dashboard
2. **Enter Target**: Input domain or IP address (e.g., `example.com` or `192.168.1.1`)
3. **Start Scan**: Click "Start Scan" button
4. **Monitor Progress**: Watch real-time scan progress
5. **View Results**: Access detailed reports and analysis

### API Usage

```python
import requests

# Start a new scan
response = requests.post('http://localhost:8000/api/scans/', 
                        json={'target': 'example.com'})
scan_id = response.json()['id']

# Check scan status
status = requests.get(f'http://localhost:8000/api/scans/{scan_id}')

# Get PDF report (when completed)
pdf = requests.get(f'http://localhost:8000/api/reports/{scan_id}/pdf')
```

## Security Features

### Vulnerability Detection
- **Port Scanning**: Comprehensive TCP/UDP port discovery
- **Service Detection**: Version and service enumeration
- **Web Application Testing**: OWASP Top 10 vulnerability scanning
- **SSL/TLS Analysis**: Certificate and configuration assessment
- **DNS Reconnaissance**: Subdomain and record enumeration

### Analysis & Scoring
- **Threat Assessment**: Vulnerability severity and impact analysis
- **Risk Scoring**: Calculated risk assessment (0-100 scale)
- **Exploitation Context**: Practical attack scenarios
- **Business Impact**: Organizational impact assessment
- **Remediation Guidance**: Prioritized fix recommendations

### Reporting
- **Executive Summaries**: Management-level reports
- **Technical Details**: In-depth vulnerability information
- **PDF Generation**: Professional report formatting
- **JSON API**: Programmatic access to all data

## 📊 Sample Results

```json
{
  "target": "example.com",
  "risk_score": 75,
  "vulnerability_count": 12,
  "critical_findings": [
    {
      "title": "SQL Injection in Login Form",
      "severity": "Critical",
      "description": "Authentication bypass via SQL injection",
      "business_impact": "Complete database compromise possible",
      "remediation": "Implement parameterized queries"
    }
  ],
  "recommendations": [
    "Patch critical vulnerabilities immediately",
    "Implement Web Application Firewall",
    "Regular security training for developers"
  ]
}
```

## Deployment

### Production Docker

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose up --scale celery_worker=3
```

### Cloud Deployment

- **Frontend**: Deploy to Vercel, Netlify, or AWS Amplify
- **Backend**: Deploy to Railway, Render, or AWS ECS
- **Database**: Use managed PostgreSQL (Supabase, AWS RDS)
- **Redis**: Use managed Redis (Redis Cloud, AWS ElastiCache)

## Performance

- **Scan Speed**: 5-10 minutes for typical websites
- **Concurrent Scans**: Up to 5 simultaneous scans
- **API Response**: Sub-second response times
- **Scalability**: Supports horizontal scaling via Docker Compose

## Configuration

### Environment Variables

#### Backend (.env)
```bash
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key
# Optional: External service API keys
ANALYSIS_API_KEY=your-key-here
SHODAN_API_KEY=your-shodan-key
```

#### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Scaling Configuration

```python
# app/config.py
MAX_CONCURRENT_SCANS = 10
SCAN_TIMEOUT_MINUTES = 45
WORKER_PREFETCH_MULTIPLIER = 2
```

## API Documentation

Full API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

- `POST /api/scans/` - Start new scan
- `GET /api/scans/{id}` - Get scan details
- `GET /api/reports/{id}/pdf` - Download PDF report
- `GET /api/reports/{id}/json` - Get JSON report

## Troubleshooting

### Common Issues

1. **Scan Fails**: Check target accessibility and firewall settings
2. **Analysis Empty**: Verify analysis service availability and configuration
3. **Port Scan Errors**: Ensure Nmap is installed and accessible
4. **Database Connection**: Verify PostgreSQL is running and accessible

### Logs and Debugging

```bash
# View all logs
docker-compose logs

# Backend logs only
docker-compose logs backend

# Celery worker logs
docker-compose logs celery_worker

# Frontend logs
docker-compose logs frontend
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is proprietary software. All rights reserved.

### Legal Notice

**IMPORTANT**: Only scan targets you have explicit permission to test. This tool is designed for authorized security testing only. Users are responsible for compliance with all applicable laws and regulations.

## Support

- **Documentation**: See docs/ directory or README files in each module
- **Issues**: Report issues through GitHub Issues
- **Technical Inquiries**: Review inline code documentation

## Roadmap

- [ ] Integration with SIEM systems
- [ ] Custom vulnerability scanning templates
- [ ] Multi-tenant support
- [ ] Enhanced reporting capabilities
- [ ] Extended integration options

---

**PHANTOM Security** - Comprehensive vulnerability detection and analysis