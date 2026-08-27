up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test-api:
	cd services/api && pytest -q

test-worker:
	cd services/worker && pytest -q

test-web:
	cd services/web && npm ci && npm test

build:
	docker build -t edgeops-api:local services/api
	docker build -t edgeops-worker:local services/worker
	docker build -t edgeops-agent:local services/agent
	docker build -t edgeops-web:local services/web

scan:
	trivy fs .

helm-lint:
	helm lint helm/edgeops

helm-template:
	helm template edgeops helm/edgeops

status:
	kubectl get pods,svc,ingress,pvc -n edgeops
