# Docker Deployment Guide

Complete guide for running QuestionsApp in Docker containers.

## 🚀 Quick Start

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Optional: Ollama running on host machine (recommended) OR use containerized Ollama

### Basic Setup (Using Host Ollama)

1. **Ensure Ollama is running on your host machine**
   ```bash
   ollama serve
   ollama pull qwen2.5:7b
   ```

2. **Start the application**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:8602
   - Backend API: http://localhost:8601
   - API Docs: http://localhost:8601/docs

### Setup with Containerized Ollama

1. **Start all services including Ollama**
   ```bash
   docker-compose --profile with-ollama up -d
   ```

2. **Pull the LLM model inside the container**
   ```bash
   docker exec questionsapp-ollama ollama pull qwen2.5:7b
   ```

3. **Update docker.env to use containerized Ollama**
   ```bash
   LLM_BASE_URL=http://ollama:11434
   ```

## 📋 Services

### Backend (FastAPI)
- **Port**: 8601
- **Container**: `questionsapp-backend`
- **Purpose**: REST API for RAG operations
- **Data**: `/app/data` (mounted from `./data`)

### Frontend (Streamlit)
- **Port**: 8602
- **Container**: `questionsapp-frontend`
- **Purpose**: Web UI for document ingestion and queries

### Ollama (Optional)
- **Port**: 11434
- **Container**: `questionsapp-ollama`
- **Purpose**: Local LLM inference
- **Data**: Docker volume `ollama_data`

## ⚙️ Configuration

### Environment Variables

Create a `.env` file from `docker.env`:
```bash
cp docker.env .env
```

Key configurations:

**LLM Settings**
```bash
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://host.docker.internal:11434
```

**Embeddings**
```bash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
```

**Processing**
```bash
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
ENABLE_OCR=true
```

### Advanced: GPU Acceleration

To use GPU for embeddings/reranking:

1. **Install NVIDIA Container Toolkit**
   ```bash
   # Ubuntu/Debian
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
       sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

2. **Update docker-compose.yml**
   Uncomment the GPU deployment section in the backend service:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```

3. **Update environment**
   ```bash
   EMBEDDING_DEVICE=cuda
   USE_GPU=true
   ```

## 🔧 Common Commands

### Start Services
```bash
# All services (using host Ollama)
docker-compose up -d

# With containerized Ollama
docker-compose --profile with-ollama up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
```

### Stop Services
```bash
docker-compose down
```

### Rebuild Containers
```bash
# Rebuild after code changes
docker-compose build

# Rebuild without cache
docker-compose build --no-cache

# Rebuild and restart
docker-compose up -d --build
```

### Check Status
```bash
docker-compose ps
```

### Access Container Shell
```bash
# Backend
docker exec -it questionsapp-backend bash

# Frontend
docker exec -it questionsapp-frontend bash
```

## 📊 Monitoring

### Health Checks
```bash
# Backend health
curl http://localhost:8601/health

# Frontend health
curl http://localhost:8602/_stcore/health

# Ollama health (if using container)
curl http://localhost:11434/api/tags
```

### View Logs
```bash
# All services
docker-compose logs -f

# Backend only
docker logs -f questionsapp-backend

# Frontend only
docker logs -f questionsapp-frontend

# Last 100 lines
docker logs questionsapp-backend --tail 100
```

## 💾 Data Persistence

Data is persisted in the following locations:

- **Application Data**: `./data/` (mounted volume)
  - Vector store: `./data/vector_store/`
  - Metadata DB: `./data/metadata/`
  - Logs: `./data/logs/`
  
- **Models**: `./models/` (mounted volume)
  - Downloaded embedding models
  
- **Ollama Data**: Docker volume `ollama_data`
  - LLM models and configurations

## 🐛 Troubleshooting

### Backend Not Starting

**Issue**: Backend fails health check
```bash
docker logs questionsapp-backend
```

**Common causes**:
- Ollama not accessible
- Port 8601 already in use
- Missing dependencies

**Solution**:
```bash
# Check Ollama connectivity
docker exec questionsapp-backend curl http://host.docker.internal:11434/api/tags

# Restart backend
docker-compose restart backend
```

### Frontend Not Connecting

**Issue**: Frontend can't reach backend

**Solution**: Update `docker.env`:
```bash
BACKEND_URL=http://backend:8601
```

### GPU Not Detected

**Issue**: CUDA errors in logs

**Check GPU availability**:
```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**Ensure**:
- NVIDIA drivers installed on host
- nvidia-container-toolkit installed
- GPU section uncommented in docker-compose.yml

### Out of Memory

**Issue**: Embedding or LLM crashes

**Solution**: Reduce batch sizes in `.env`:
```bash
EMBEDDING_BATCH_SIZE=16  # Lower from 32
LLM_MODEL=qwen2.5:3b     # Use smaller model
```

### Slow Document Processing

**Issue**: Ingestion takes too long

**Solutions**:
1. Disable OCR if not needed:
   ```bash
   ENABLE_OCR=false
   ```

2. Increase workers:
   ```bash
   MAX_WORKERS=8
   ```

3. Use GPU for embeddings:
   ```bash
   EMBEDDING_DEVICE=cuda
   ```

## 🔄 Updates and Maintenance

### Update Application Code
```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Update Dependencies
```bash
# Update backend requirements
cd backend
pip-compile requirements.txt
cd ..
docker-compose build --no-cache backend
```

### Backup Data
```bash
# Backup application data
tar -czf questionsapp-backup-$(date +%Y%m%d).tar.gz data/

# Backup Ollama models (if using container)
docker run --rm -v ollama_data:/data -v $(pwd):/backup ubuntu \
    tar czf /backup/ollama-backup-$(date +%Y%m%d).tar.gz /data
```

### Clean Up
```bash
# Remove stopped containers
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker image prune -a

# Full cleanup
docker system prune -a --volumes
```

## 🌐 Production Deployment

### Security Checklist

- [ ] Change default ports
- [ ] Enable authentication
- [ ] Use HTTPS/TLS
- [ ] Restrict CORS origins
- [ ] Use secrets management
- [ ] Enable rate limiting
- [ ] Configure firewall rules
- [ ] Use non-root users in containers
- [ ] Enable audit logging
- [ ] Regular security updates

### Performance Optimization

1. **Use GPU** for embeddings and reranking
2. **Increase workers** in production:
   ```yaml
   API_WORKERS=4
   ```
3. **Use better embedding model**:
   ```bash
   EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
   ```
4. **Enable caching** in Streamlit
5. **Use reverse proxy** (nginx) for load balancing

### Scaling

For high-load production:
```bash
docker-compose up -d --scale backend=3
```

## 📝 License

See main repository LICENSE file.
