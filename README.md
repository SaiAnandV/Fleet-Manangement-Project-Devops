# Fleet Management & Vehicle Maintenance Tracking Portal

**Course:** DevOps & Full Stack – B.Tech IV Year I Sem (2026-27) – Course Project

## 1. Objectives
- Maintain a central register of fleet vehicles and their assigned drivers.
- Schedule, log and complete maintenance services; flag overdue services.
- Show fleet health and maintenance spend on a dashboard.
- Demonstrate a DevOps pipeline: **GitHub → Docker → Kubernetes**.

## 2. Technology Stack
| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript (`static/index.html`), calls the REST API with `fetch` |
| Backend | Python 3.12, Flask 3 (REST API), Gunicorn (production server) |
| Database | SQLite (file on a persistent volume) |
| Testing / CI | `unittest`, GitHub Actions |
| Containerisation | Docker, Docker Compose |
| Orchestration | Kubernetes (Deployment, Service, PVC) |

## 3. Architecture
```
 Browser ──HTTP──► K8s Service (NodePort 30080 → 80)
                        │
                        ▼
                 Pod: Flask + Gunicorn (:5000)
                  ├─ GET /            → static/index.html (frontend)
                  └─ /api/*           → REST endpoints
                        │
                        ▼
                 SQLite /data/fleet.db  ◄── PersistentVolumeClaim (1Gi)
```
Tables: `drivers`, `vehicles` (→ driver), `maintenance` (→ vehicle, cascade delete).

## 4. Project Structure
```
app.py              Flask app + REST API (application factory create_app)
static/index.html   Frontend (dashboard, vehicles, maintenance, drivers)
seed.py             Optional sample data
tests/test_api.py   Automated API tests
Dockerfile, docker-compose.yml, .dockerignore
k8s/deployment.yaml PVC + Deployment (probes, resource limits)
k8s/service.yaml    NodePort Service
.github/workflows/ci.yml   Runs tests and builds the image on every push
```

## 5. REST API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness/readiness check |
| GET/POST | `/api/vehicles` (`?q=` search) | List / add vehicle |
| GET/PUT/DELETE | `/api/vehicles/<id>` | Read / update / delete |
| GET/POST | `/api/maintenance` (`?vehicle_id=`) | List / add service record |
| PATCH | `/api/maintenance/<id>/complete` | Mark service completed |
| DELETE | `/api/maintenance/<id>` | Delete record |
| GET/POST, DELETE | `/api/drivers`, `/api/drivers/<id>` | Manage drivers |
| GET | `/api/dashboard` | Totals, overdue count, cost, services due in 14 days |

Validation: required fields, unique registration/licence numbers (409), valid dates and non-negative numbers (400).

## 6. Run Locally (no Docker)
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py          # optional sample data
python app.py           # open http://localhost:5000
python -m unittest discover -s tests -v    # run tests
```

## 7. GitHub & Version Control
```bash
git init
git add .
git commit -m "feat: Flask API for vehicles, drivers, maintenance"
git branch -M main
git remote add origin https://github.com/<your-username>/fleet-portal.git
git push -u origin main
```
Use small, meaningful commits (e.g. `feat: add dashboard`, `test: add API tests`, `ci: add workflow`, `docs: add README`, `chore: add k8s manifests`). The GitHub Actions workflow runs the tests and builds the Docker image on every push.

## 8. Docker
```bash
docker build -t fleet-portal:latest .
docker run -d --name fleet -p 5000:5000 -v fleet-data:/data fleet-portal:latest
# open http://localhost:5000      (check: curl localhost:5000/api/health)
# load sample data:  docker exec fleet python seed.py
# or simply:  docker compose up --build
```
The image runs as a non-root user, stores data in the `/data` volume and includes a HEALTHCHECK.

## 9. Kubernetes Deployment
Works on Docker Desktop Kubernetes, minikube or kind. The image must be available to the cluster:
```bash
# minikube:  eval $(minikube docker-env) && docker build -t fleet-portal:latest .
# kind:      docker build -t fleet-portal:latest . && kind load docker-image fleet-portal:latest

kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods,svc,pvc                 # pod should be Running / Ready 1/1
kubectl exec deploy/fleet-portal -- python seed.py     # optional sample data
```
Access the app:
- minikube: `minikube service fleet-portal-svc --url`
- Docker Desktop / others: `http://localhost:30080`
- Fallback: `kubectl port-forward svc/fleet-portal-svc 8080:80` → http://localhost:8080

Notes: one replica is used on purpose because SQLite is file-based and the PVC is `ReadWriteOnce`. Scaling out would need a client/server database such as PostgreSQL.
Clean up: `kubectl delete -f k8s/`.

## 10. Verification Checklist
- [ ] `python -m unittest discover -s tests` → all tests pass
- [ ] `docker build` succeeds; container responds on `/api/health`
- [ ] `kubectl get pods` shows `1/1 Running`; app opens via the Service
- [ ] Add a vehicle, schedule a service, mark it completed – the dashboard updates
