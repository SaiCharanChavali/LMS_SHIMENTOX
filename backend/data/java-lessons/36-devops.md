## Introduction to DevOps
**DevOps** is a culture and set of practices that bring development and operations together to deliver software **faster and more reliably**. Instead of "developers write code, operations run it", one team owns the full lifecycle with heavy automation.

The DevOps loop: **Plan → Code → Build → Test → Release → Deploy → Operate → Monitor** → back to Plan.

Key practices:
- **Continuous Integration (CI)** - merge small changes often; every change is built and tested automatically.
- **Continuous Delivery/Deployment (CD)** - every passing change is releasable (delivery) or released automatically (deployment).
- **Infrastructure as Code** - servers and networks defined in versioned files (Terraform, Docker Compose, Kubernetes YAML).
- **Monitoring and feedback** - logs, metrics, alerts and post-incident reviews.

## Linux introduction
Most servers, containers and cloud VMs run **Linux**. Key concepts:
- Everything is a file; the filesystem starts at `/` (`/home`, `/etc` for config, `/var/log` for logs, `/opt` for apps, `/tmp`).
- **Users and groups**; `root` is the superuser - use `sudo` for administrative commands and run applications as unprivileged users.
- **Permissions**: read (r=4), write (w=2), execute (x=1) for owner, group and others - `chmod 750 app.sh` means `rwxr-x---`.
- **Processes** have IDs (PIDs); **services** are managed by `systemd`.
- **Package managers**: `apt` (Ubuntu/Debian), `dnf`/`yum` (RHEL/Fedora).

## Linux commands for DevOps
| Task | Commands |
| --- | --- |
| Navigate | `pwd`, `ls -la`, `cd /var/log` |
| Files | `cp`, `mv`, `rm -r`, `mkdir -p`, `touch`, `cat`, `less`, `head -n 20`, `tail -f app.log` |
| Search | `grep -i "error" app.log`, `find / -name "*.jar"` |
| Permissions | `chmod 640 file`, `chown app:app file` |
| Processes | `ps aux`, `top`/`htop`, `kill <pid>`, `kill -9 <pid>` |
| Services | `systemctl status nginx`, `systemctl restart app`, `journalctl -u app -f` |
| Disk/memory | `df -h`, `du -sh *`, `free -h` |
| Network | `ip a`, `ss -tulpn` (listening ports), `curl -I https://site`, `ping`, `nslookup`/`dig` |
| Packages | `sudo apt update && sudo apt install openjdk-21-jre` |
| Archives | `tar -czf backup.tar.gz dir/`, `tar -xzf backup.tar.gz` |
| Environment | `export DB_USER=app`, `echo $PATH`, `env` |
| Redirect | `cmd > out.txt 2>&1` (stdout and stderr to a file), `cmd >> out.txt` (append) |

Commands can be chained with a pipe, which sends one command's output into the next: `grep ERROR app.log | wc -l` counts error lines.

Running a Spring Boot JAR as a service:

```ini
# /etc/systemd/system/training-api.service
[Unit]
Description=Training API
After=network.target

[Service]
User=trainingapp
EnvironmentFile=/etc/training-api/env
ExecStart=/usr/bin/java -jar /opt/training-api/app.jar --spring.profiles.active=prod
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now training-api
journalctl -u training-api -f
```

## SSH
**SSH (Secure Shell)** gives encrypted remote access to servers.

```bash
ssh-keygen -t ed25519 -C "asha@laptop"         # create a key pair (~/.ssh/id_ed25519 + .pub)
ssh-copy-id ubuntu@203.0.113.10                 # install the public key on the server
ssh ubuntu@203.0.113.10                          # log in
ssh -i ~/.ssh/aws-key.pem ec2-user@<ip>          # use a specific key
scp build/libs/app.jar ubuntu@<ip>:/opt/training-api/   # copy files
ssh -L 3307:localhost:3306 ubuntu@<ip>           # tunnel: local 3307 → server's MySQL
```

Hardening: use keys instead of passwords (`PasswordAuthentication no`), disable root login, restrict SSH to known IPs with a firewall, keep private keys private (`chmod 600`).

## Docker
**Docker** packages an application and everything it needs (runtime, libraries, config defaults) into an **image**, which runs as an isolated **container** - identical on a laptop, CI and production. Containers share the host kernel, so they start in seconds and are lighter than virtual machines.

| Term | Meaning |
| --- | --- |
| Image | Read-only template built from a Dockerfile, in layers |
| Container | A running instance of an image |
| Dockerfile | Instructions to build an image |
| Registry | Image storage (Docker Hub, Amazon ECR, Azure ACR, GHCR) |
| Volume | Persistent storage that outlives containers |
| Network | Lets containers talk by name |

A multi-stage Dockerfile for Spring Boot:

```dockerfile
# Stage 1: build
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY . .
RUN ./gradlew bootJar --no-daemon

# Stage 2: run (smaller image, no JDK or source)
FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --system appuser
COPY --from=build /src/build/libs/*.jar app.jar
USER appuser
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

```bash
docker build -t training-api:1.0.0 .
docker run -d --name api -p 8080:8080 -e SPRING_PROFILES_ACTIVE=prod -e DB_PASSWORD=... training-api:1.0.0
docker ps                      # running containers
docker logs -f api             # follow logs
docker exec -it api sh         # shell inside
docker stop api && docker rm api
docker images; docker push registry.example.com/training-api:1.0.0
```

Best practices: small base images, multi-stage builds, a `.dockerignore`, non-root users, **no secrets in images** (pass at runtime), pin versions, one process per container.

## Docker Compose
**Docker Compose** defines and runs multi-container applications with one YAML file - ideal for local development.

```yaml
# compose.yaml
services:
  db:
    image: mysql:8.4
    environment:
      MYSQL_DATABASE: training_db
      MYSQL_USER: app
      MYSQL_PASSWORD: ${DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
    volumes:
      - db-data:/var/lib/mysql          # persistent data
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      retries: 5

  api:
    build: ./backend
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://db:3306/training_db     # "db" = service name
      SPRING_DATASOURCE_USERNAME: app
      SPRING_DATASOURCE_PASSWORD: ${DB_PASSWORD}
    depends_on:
      db:
        condition: service_healthy     # wait until MySQL is ready, not just started
    ports:
      - "8080:8080"

  web:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - api

volumes:
  db-data:
```

```bash
docker compose up -d --build     # start everything
docker compose logs -f api
docker compose down              # stop (add -v to delete volumes - and data!)
```

Values like `${DB_PASSWORD}` come from a `.env` file that is **not** committed.

## Kubernetes basics
**Kubernetes (K8s)** orchestrates containers across a cluster of machines: scheduling, scaling, self-healing, rolling updates and service discovery.

| Object | Purpose |
| --- | --- |
| Pod | Smallest unit; one or more containers sharing network/storage |
| Deployment | Keeps N replicas of a pod running; rolling updates and rollbacks |
| Service | Stable name/IP that load-balances to pods |
| Ingress | HTTP routing from outside into services |
| ConfigMap / Secret | Configuration and sensitive values injected into pods |
| Namespace | Logical isolation within a cluster |

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: training-api
spec:
  replicas: 3
  selector:
    matchLabels: { app: training-api }
  template:
    metadata:
      labels: { app: training-api }
    spec:
      containers:
        - name: api
          image: registry.example.com/training-api:1.0.0
          ports: [{ containerPort: 8080 }]
          envFrom: [{ secretRef: { name: training-api-secrets } }]
          readinessProbe:
            httpGet: { path: /actuator/health/readiness, port: 8080 }
          livenessProbe:
            httpGet: { path: /actuator/health/liveness, port: 8080 }
          resources:
            requests: { cpu: "250m", memory: "512Mi" }
            limits: { memory: "1Gi" }
---
apiVersion: v1
kind: Service
metadata:
  name: training-api
spec:
  selector: { app: training-api }
  ports: [{ port: 80, targetPort: 8080 }]
```

```bash
kubectl apply -f k8s/
kubectl get pods
kubectl logs -f deploy/training-api
kubectl scale deploy/training-api --replicas=5
kubectl rollout undo deploy/training-api
```

Managed Kubernetes: Amazon EKS, Azure AKS, Google GKE. For small apps, simpler platforms (App Service, ECS, Cloud Run) are often enough.

## Jenkins
**Jenkins** is a self-hosted, open-source automation server with a large plugin ecosystem. Pipelines are defined as code in a `Jenkinsfile`:

```groovy
pipeline {
    agent any
    environment {
        IMAGE = "registry.example.com/training-api:${env.BUILD_NUMBER}"
    }
    stages {
        stage('Checkout') { steps { checkout scm } }
        stage('Build & Test') {
            steps { sh './gradlew clean build' }
            post { always { junit 'build/test-results/test/*.xml' } }
        }
        stage('Docker Image') {
            steps {
                sh "docker build -t $IMAGE ."
                withCredentials([usernamePassword(credentialsId: 'registry', usernameVariable: 'U', passwordVariable: 'P')]) {
                    sh 'echo $P | docker login registry.example.com -u $U --password-stdin'
                    sh "docker push $IMAGE"
                }
            }
        }
        stage('Deploy to Staging') {
            when { branch 'main' }
            steps { sh "kubectl set image deploy/training-api api=$IMAGE -n staging" }
        }
    }
}
```

## GitHub Actions
GitHub Actions (introduced in Module 25) runs pipelines inside GitHub, with no server to maintain:

```yaml
name: CI/CD
on:
  push:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: '21', cache: gradle }
      - run: ./gradlew build
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - run: |
          docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
          docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
```

| | Jenkins | GitHub Actions |
| --- | --- | --- |
| Hosting | Self-hosted (you maintain it) | Managed by GitHub (or self-hosted runners) |
| Config | Jenkinsfile (Groovy) | YAML in `.github/workflows` |
| Ecosystem | Thousands of plugins | Marketplace actions |
| Best for | Complex on-premises/enterprise setups | Repositories already on GitHub |

## CI/CD pipeline
A good pipeline:
1. **Trigger** on pull requests and merges to `main`.
2. **Build** and run static checks (compile, lint, formatting).
3. **Test**: unit, integration (Testcontainers), and security scans (dependency vulnerabilities, secrets).
4. **Package** once into an immutable, versioned artifact or image (tag with the commit SHA).
5. **Deploy to staging**; run database migrations and smoke/E2E tests.
6. **Approve and promote** the **same** artifact to production (blue-green, canary or rolling).
7. **Verify** health checks and key user journeys; **roll back** automatically or quickly on failure.
8. **Monitor** metrics, logs and alerts.

Build once, deploy many: never rebuild separately for production, or you deploy something you did not test.

## Nginx
**Nginx** is a high-performance web server and reverse proxy. A typical full-stack configuration serves the React build and proxies the API:

```nginx
server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;              # force HTTPS
}

server {
    listen 443 ssl;
    server_name app.example.com;
    ssl_certificate     /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;

    root /var/www/training-ui;                          # React dist/
    index index.html;

    location / {
        try_files $uri /index.html;                     # client-side routing fallback
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080;               # Spring Boot
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~* \.(js|css|png|svg|woff2)$ {
        expires 30d;                                    # long cache for fingerprinted assets
    }
}
```

```bash
sudo nginx -t                  # test configuration
sudo systemctl reload nginx
```

For load balancing, define an `upstream` block with several backend servers. Set `server.forward-headers-strategy=framework` in Spring Boot so it understands the forwarded headers.

## Common mistakes
- Running containers or services as root.
- Baking secrets into images or committing `.env` files.
- `depends_on` without health checks, so the API starts before the database is ready.
- Rebuilding artifacts per environment.
- No rollback plan; no monitoring after deploy.

## Practice exercise
1. On a Linux VM (or WSL), install Java and run the Training API as a `systemd` service with logs in `journalctl`.
2. Write a multi-stage Dockerfile for the API and an Nginx-based image for the React app.
3. Create a Compose file with MySQL (volume + health check), API and web; start the whole stack.
4. Write a GitHub Actions or Jenkins pipeline that tests, builds and pushes an image tagged with the commit SHA.
5. Configure Nginx to serve the React build with a routing fallback and proxy `/api`.
6. (Optional) Deploy the API to a local Kubernetes cluster (kind/minikube) with probes and 2 replicas.

## Key takeaways
- DevOps unites development and operations through automation, CI/CD and feedback.
- Know core Linux commands, permissions, processes, services and SSH key-based access.
- Docker packages apps as images; Compose runs multi-container stacks; Kubernetes orchestrates at scale.
- Jenkins and GitHub Actions implement pipelines: build once, test, deploy, verify, roll back.
- Nginx serves static frontends, proxies APIs and terminates TLS.
