## Introduction to cloud deployment
**Cloud computing** provides servers, storage, databases and networking on demand, paid for as you use them. Instead of buying hardware, you provision resources in minutes and scale them up or down.

| Model | You manage | Provider manages | Examples |
| --- | --- | --- | --- |
| **IaaS** (Infrastructure) | OS, runtime, app, data | Hardware, network, virtualisation | AWS EC2, Azure VMs |
| **PaaS** (Platform) | App and data | OS, runtime, scaling, patching | Azure App Service, AWS Elastic Beanstalk |
| **SaaS** (Software) | Usage and configuration | Everything | Gmail, Salesforce |
| Containers / serverless | Image or function | Cluster/servers | ECS, EKS, Cloud Run, Lambda |

Major providers: **AWS**, **Microsoft Azure**, **Google Cloud**. Core concepts: **regions** (geographic locations) and **availability zones** (isolated data centres within a region - deploy across several for resilience), **IAM** (identity and access management), **VPC/VNet** (private networks), **security groups** (firewalls) and **billing alerts**.

Cost safety: use free tiers for practice, set budget alerts and delete resources you no longer need.

## Deploy Spring Boot
Prepare the application for any cloud:
1. Externalise configuration: `SPRING_PROFILES_ACTIVE`, `SPRING_DATASOURCE_URL`, credentials from environment variables or a secrets service.
2. Expose health checks (`/actuator/health`) for the platform's load balancer.
3. Log to standard output; let the platform collect logs.
4. Package as an executable JAR (`./gradlew bootJar`) or container image.
5. Run database migrations (Flyway) as part of release.

Deployment targets: a VM (EC2) with systemd, a PaaS (App Service, Elastic Beanstalk), or containers (ECS, AKS, EKS).

## Deploy React
A React build is static files, so hosting is cheap and simple:

```bash
VITE_API_URL=https://api.example.com/api npm run build      # outputs dist/
```

Options: AWS S3 + CloudFront, Azure Static Web Apps, Netlify, Vercel, or Nginx on a VM. Configure a fallback to `index.html` for client-side routes and long cache headers for fingerprinted assets. Remember: everything in the bundle is public.

## AWS EC2
**Amazon EC2** provides virtual machines ("instances").

Steps to run the API on EC2:
1. Launch an instance (e.g. Ubuntu, `t3.micro` for practice) in a region near your users.
2. Create or select a **key pair** for SSH.
3. Configure the **security group**: allow SSH (22) only from your IP, HTTP (80) and HTTPS (443) from anywhere; do not expose 8080 or 3306 publicly.
4. Connect and install Java (or Docker):

```bash
ssh -i training-key.pem ubuntu@<public-ip>
sudo apt update && sudo apt install -y openjdk-21-jre nginx
scp -i training-key.pem build/libs/app.jar ubuntu@<public-ip>:/opt/training-api/app.jar
```

5. Run the JAR as a systemd service (Module 36) and put Nginx in front as a reverse proxy.
6. Attach an **Elastic IP** (static address) and an **IAM role** if the app needs AWS services (instead of access keys).

For scaling and resilience, use an Auto Scaling group behind an Application Load Balancer across several availability zones.

## AWS S3
**Amazon S3** is object storage: unlimited files ("objects") in **buckets**, addressed by keys.

Uses: hosting the React build, storing uploaded course materials and certificates, backups and logs.

```java
// Spring Boot upload with AWS SDK v2
S3Client s3 = S3Client.builder().region(Region.AP_SOUTH_1).build();   // credentials from the IAM role
s3.putObject(PutObjectRequest.builder()
        .bucket("training-materials")
        .key("courses/42/" + UUID.randomUUID() + ".pdf")
        .contentType("application/pdf")
        .build(),
    RequestBody.fromInputStream(file.getInputStream(), file.getSize()));
```

Security: keep **Block Public Access** on; serve public website files through CloudFront; give users time-limited **pre-signed URLs** for private downloads; enable versioning and encryption. Never put AWS access keys in code or the frontend.

## AWS RDS
**Amazon RDS** is a managed relational database service (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server). AWS handles provisioning, patching, automated backups, and optional Multi-AZ standby replicas for failover.

Steps:
1. Create an RDS MySQL instance in a **private subnet** (not publicly accessible).
2. Allow inbound 3306 **only** from the application's security group.
3. Enable automated backups and choose a retention period; enable Multi-AZ for production.
4. Store credentials in **AWS Secrets Manager** (or SSM Parameter Store) and inject them as environment variables.
5. Point Spring Boot at the endpoint:

```properties
spring.datasource.url=jdbc:mysql://training-db.xxxxxxx.ap-south-1.rds.amazonaws.com:3306/training_db
spring.datasource.username=${DB_USER}
spring.datasource.password=${DB_PASSWORD}
```

Add read replicas for read-heavy workloads. Test restoring a snapshot - a backup is only proven once restored.

## Azure App Service
**Azure App Service** is a PaaS for web apps: you deploy code or a container; Azure runs, patches and scales it.

```bash
az login
az group create --name training-rg --location centralindia
az appservice plan create --name training-plan --resource-group training-rg --sku B1 --is-linux
az webapp create --name training-api-demo --resource-group training-rg \
    --plan training-plan --runtime "JAVA:21-java21"
az webapp config appsettings set --name training-api-demo --resource-group training-rg \
    --settings SPRING_PROFILES_ACTIVE=prod DB_USER=app
az webapp deploy --name training-api-demo --resource-group training-rg \
    --src-path build/libs/app.jar --type jar
```

Features: deployment slots (staging → swap to production with no downtime), autoscaling, managed TLS certificates, built-in logging and Application Insights monitoring, integration with Azure Key Vault and Azure Database for MySQL. GitHub Actions can deploy on every merge.

## Docker deployment
Containers make deployments consistent across environments:
1. Build and tag the image with a version or commit SHA.
2. Push it to a registry: Amazon ECR, Azure Container Registry, GitHub Container Registry, Docker Hub.
3. Run it on a platform that fits your needs (see the list below).

Where to run containers:
- A VM with Docker/Compose (simple).
- **AWS ECS/Fargate** or **Azure Container Apps** (managed containers, no cluster to manage).
- **EKS/AKS** Kubernetes (most control, most complexity).
- **Azure App Service for Containers**.

```bash
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com
docker tag training-api:1.0.0 <account>.dkr.ecr.ap-south-1.amazonaws.com/training-api:1.0.0
docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/training-api:1.0.0
```

Pass configuration and secrets at runtime, configure health checks and set CPU/memory limits.

## Domain configuration
Users should reach `https://app.example.com`, not an IP address.
1. Buy a domain from a registrar (Route 53, GoDaddy, Namecheap).
2. Manage DNS in a DNS service (Route 53, Azure DNS, Cloudflare).
3. Create records:

| Record | Points | Example |
| --- | --- | --- |
| A | Name → IPv4 address | `api.example.com → 203.0.113.10` |
| AAAA | Name → IPv6 address | |
| CNAME | Name → another name | `www.example.com → example.com`, `app → xyz.cloudfront.net` |
| ALIAS/ANAME | Root domain → load balancer/CDN | `example.com → my-alb...` |
| TXT | Verification, SPF | domain ownership checks |

DNS changes propagate according to the record's **TTL** (time to live). Update `VITE_API_URL`, CORS allowed origins and OAuth redirect URIs to the real domain.

## SSL certificate
**HTTPS** (TLS) encrypts traffic between browser and server and proves the server's identity; browsers mark HTTP sites "Not secure", and secure cookies, HTTP/2 and many APIs require it.

Ways to get a certificate:
- **Let's Encrypt** (free) with Certbot on your Nginx server: `sudo certbot --nginx -d app.example.com` - it configures Nginx and auto-renews every ~60-90 days.
- **AWS Certificate Manager** - free certificates for ALB and CloudFront, renewed automatically.
- **Azure App Service managed certificates** / Key Vault.

After enabling HTTPS: redirect HTTP to HTTPS, enable **HSTS** (`Strict-Transport-Security` header), mark cookies `Secure`, and monitor certificate expiry.

## A complete production checklist
- Frontend on CDN/static hosting with HTTPS and routing fallback.
- API on a PaaS, VMs or containers across availability zones, behind a load balancer with health checks.
- Managed database in a private network with backups, tested restores and least-privilege credentials.
- Secrets in a secrets manager; no credentials in code, images or the frontend.
- Domain with DNS records and TLS certificates; HTTP redirected to HTTPS.
- CI/CD pipeline deploying an immutable artifact with a rollback plan.
- Monitoring, logs, alerts and budget alerts.

## Common mistakes
- Opening database ports to the internet.
- Hard-coded AWS/Azure keys in code instead of IAM roles/managed identities.
- Public S3 buckets for private files.
- Forgetting to update CORS and OAuth redirect URLs after moving to a real domain.
- Leaving test resources running and receiving a surprise bill.

## Practice exercise
Deploy your full-stack Training Portal (use free tiers and delete resources afterwards):
1. Database: RDS MySQL (or Azure Database for MySQL) in a private network.
2. API: EC2 with systemd + Nginx, **or** Azure App Service, **or** a container on ECS/Container Apps.
3. Uploaded course materials stored in S3 with pre-signed download URLs.
4. React build on S3 + CloudFront or Azure Static Web Apps.
5. A domain (or free subdomain) with DNS records and HTTPS certificates.
6. Write a deployment runbook: steps, configuration, verification checks and rollback.

## Key takeaways
- IaaS gives control, PaaS reduces operations, containers give portability; choose per need.
- Spring Boot deploys as a JAR or image with externalised configuration and health checks; React deploys as static files.
- EC2 runs VMs, S3 stores objects, RDS manages databases; Azure App Service is a managed web app platform.
- Keep databases private, secrets in managed stores and access via roles.
- Configure DNS records and TLS certificates, and redirect all traffic to HTTPS.
